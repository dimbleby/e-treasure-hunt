terraform {
  required_version = "~> 1.5"
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.9"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  backend "azurerm" {
    storage_account_name = "treasurebackend"
    container_name       = "terraformstate"
    key                  = "e-treasure-hunt"
    use_azuread_auth     = true
  }
}

provider "azurerm" {
  features {}
  storage_use_azuread = true
  subscription_id     = var.subscription_id
}

resource "random_password" "azuread_password" {
  length      = 16
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

data "azuread_domains" "aad_domains" {
  only_default = true
}

resource "azuread_user" "database_admin" {
  user_principal_name = "${var.app_name}@${data.azuread_domains.aad_domains.domains.0.domain_name}"
  display_name        = "${var.app_name} database admin"
  password            = random_password.azuread_password.result
}

resource "azurerm_resource_group" "treasure" {
  name     = "${var.app_name}-rg"
  location = var.region
}

resource "azurerm_storage_account" "treasure" {
  name                            = replace(var.app_name, "/\\W/", "")
  resource_group_name             = azurerm_resource_group.treasure.name
  location                        = azurerm_resource_group.treasure.location
  account_replication_type        = "LRS"
  account_tier                    = "Standard"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  default_to_oauth_authentication = true
}

resource "azurerm_storage_container" "media" {
  name                  = "media"
  storage_account_id    = azurerm_storage_account.treasure.id
  container_access_type = "private"
}

resource "azurerm_mssql_server" "treasure" {
  name                                 = "${var.app_name}-sql-server"
  resource_group_name                  = azurerm_resource_group.treasure.name
  location                             = azurerm_resource_group.treasure.location
  version                              = "12.0"
  connection_policy                    = "Redirect"
  minimum_tls_version                  = "1.2"
  outbound_network_restriction_enabled = true
  azuread_administrator {
    login_username              = "AzureAD Admin"
    object_id                   = azuread_user.database_admin.object_id
    azuread_authentication_only = true
  }
}

resource "azurerm_mssql_database" "treasure" {
  name                                = "treasurehunt"
  server_id                           = azurerm_mssql_server.treasure.id
  sku_name                            = "Basic"
  transparent_data_encryption_enabled = true
}

resource "azurerm_redis_cache" "treasure" {
  name                 = "${var.app_name}-cache"
  location             = var.region
  resource_group_name  = azurerm_resource_group.treasure.name
  capacity             = 0
  family               = "C"
  sku_name             = "Basic"
  non_ssl_port_enabled = false
  minimum_tls_version  = "1.2"

  redis_configuration {
    # active_directory_authentication_enabled = true
    authentication_enabled = true
  }
}

resource "azurerm_service_plan" "treasure" {
  name                = "${var.app_name}-plan"
  location            = azurerm_resource_group.treasure.location
  resource_group_name = azurerm_resource_group.treasure.name
  os_type             = "Linux"
  sku_name            = "B1"
}

resource "random_password" "secret_key" {
  length      = 16
  min_lower   = 1
  min_upper   = 1
  min_numeric = 1
}

resource "azurerm_linux_web_app" "treasure" {
  name                = var.app_name
  resource_group_name = azurerm_resource_group.treasure.name
  location            = azurerm_resource_group.treasure.location
  service_plan_id     = azurerm_service_plan.treasure.id

  app_settings = {
    APP_URL            = "${var.app_name}.azurewebsites.net"
    ARCGIS_API_KEY     = var.arcgis_api_key
    AZURE_ACCOUNT_NAME = azurerm_storage_account.treasure.name
    AZURE_CONTAINER    = azurerm_storage_container.media.name
    DBHOST             = azurerm_mssql_server.treasure.fully_qualified_domain_name
    DBNAME             = azurerm_mssql_database.treasure.name
    DEPLOYMENT         = "AZURE"
    GM_API_KEY         = var.google_maps_api_key
    PRE_BUILD_COMMAND  = "prebuild.sh"
    SECRET_KEY         = random_password.secret_key.result
    CACHE_PASSWORD     = azurerm_redis_cache.treasure.primary_access_key
    CACHE_URL          = azurerm_redis_cache.treasure.hostname
  }

  https_only = true

  site_config {
    always_on           = false
    minimum_tls_version = "1.3"
    ftps_state          = "Disabled"
    http2_enabled       = true
    app_command_line    = "daphne -b 0.0.0.0 treasure.asgi:application"
    application_stack {
      python_version = "3.12"
    }
  }

  identity {
    type = "SystemAssigned"
  }
}

# Pointless without <https://github.com/django/channels_redis/issues/386>.
# resource "azurerm_redis_cache_access_policy_assignment" "treasure" {
#   name               = var.app_name
#   redis_cache_id     = azurerm_redis_cache.treasure.id
#   access_policy_name = "Data Owner"
#   object_id          = azurerm_linux_web_app.treasure.identity.0.principal_id
#   object_id_alias    = "Treasure hunt"
# }

resource "azurerm_role_assignment" "storage_contributor" {
  scope                = azurerm_storage_account.treasure.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_web_app.treasure.identity.0.principal_id
}

# Run terraform apply twice, first with the more permissive block, and then with the two sets of
# targeted rules.
#
# Only make this change after using Cloud Shell to grant permissions to the app service identity,
# per instructions given by the outputs.

# resource "azurerm_mssql_firewall_rule" "treasure" {
#   name             = "Allow Azure services"
#   server_id        = azurerm_mssql_server.treasure.id
#   start_ip_address = "0.0.0.0"
#   end_ip_address   = "0.0.0.0"
# }

resource "azurerm_mssql_firewall_rule" "treasure" {
  for_each         = toset(azurerm_linux_web_app.treasure.possible_outbound_ip_address_list)
  name             = "app-service-${each.key}"
  server_id        = azurerm_mssql_server.treasure.id
  start_ip_address = each.key
  end_ip_address   = each.key
}

resource "azurerm_redis_firewall_rule" "treasure" {
  for_each            = toset(azurerm_linux_web_app.treasure.possible_outbound_ip_address_list)
  name                = "appservice_${replace(each.key, "/\\./", "_")}"
  resource_group_name = azurerm_resource_group.treasure.name
  redis_cache_name    = azurerm_redis_cache.treasure.name
  start_ip            = each.key
  end_ip              = each.key
}
