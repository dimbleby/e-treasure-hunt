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

# NB force new password by:
# terraform taint random_password.azuread_password
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

resource "azurerm_virtual_network" "treasure" {
  name                = "${var.app_name}-vnet"
  resource_group_name = azurerm_resource_group.treasure.name
  location            = azurerm_resource_group.treasure.location
  address_space       = ["10.0.0.0/16"]
}

resource "azurerm_subnet" "treasure" {
  name                            = "treasure"
  resource_group_name             = azurerm_resource_group.treasure.name
  virtual_network_name            = azurerm_virtual_network.treasure.name
  address_prefixes                = ["10.0.1.0/24"]
  default_outbound_access_enabled = false
  delegation {
    name = "appservice"
    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

resource "azurerm_subnet" "private" {
  name                            = "private-endpoints"
  resource_group_name             = azurerm_resource_group.treasure.name
  virtual_network_name            = azurerm_virtual_network.treasure.name
  address_prefixes                = ["10.0.2.0/24"]
  default_outbound_access_enabled = false
}

resource "azurerm_private_dns_zone" "redis" {
  name                = "privatelink.redis.azure.net"
  resource_group_name = azurerm_resource_group.treasure.name
}

resource "azurerm_private_dns_zone" "sql" {
  name                = "privatelink.database.windows.net"
  resource_group_name = azurerm_resource_group.treasure.name
}

resource "azurerm_user_assigned_identity" "webapp" {
  name                = "${var.app_name}-webapp-identity"
  location            = azurerm_resource_group.treasure.location
  resource_group_name = azurerm_resource_group.treasure.name
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

resource "azurerm_role_assignment" "storage_contributor" {
  scope                = azurerm_storage_account.treasure.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.webapp.principal_id
}

resource "azurerm_mssql_server" "treasure" {
  name                                 = "${var.app_name}-sql-server"
  resource_group_name                  = azurerm_resource_group.treasure.name
  location                             = azurerm_resource_group.treasure.location
  version                              = "12.0"
  connection_policy                    = "Default"
  minimum_tls_version                  = "1.2"
  outbound_network_restriction_enabled = true
  public_network_access_enabled        = false
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

resource "azurerm_private_endpoint" "sql" {
  name                = "${var.app_name}-sql-pe"
  location            = azurerm_resource_group.treasure.location
  resource_group_name = azurerm_resource_group.treasure.name
  subnet_id           = azurerm_subnet.private.id

  private_service_connection {
    name                           = "${var.app_name}-sql-pe"
    private_connection_resource_id = azurerm_mssql_server.treasure.id
    subresource_names              = ["sqlServer"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name = "default"
    private_dns_zone_ids = [
      azurerm_private_dns_zone.sql.id,
    ]
  }
}

# NB need manually to grant access to the web app identity
# <https://github.com/hashicorp/terraform-provider-azurerm/issues/30938>
resource "azurerm_managed_redis" "treasure" {
  name                = "${var.app_name}-cache"
  location            = azurerm_resource_group.treasure.location
  resource_group_name = azurerm_resource_group.treasure.name
  sku_name            = "Balanced_B0"

  default_database {
    access_keys_authentication_enabled = false
    clustering_policy                  = "EnterpriseCluster"
    eviction_policy                    = "VolatileLRU"
  }
}

resource "azurerm_private_endpoint" "redis" {
  name                = "${var.app_name}-cache-pe"
  location            = azurerm_resource_group.treasure.location
  resource_group_name = azurerm_resource_group.treasure.name
  subnet_id           = azurerm_subnet.private.id

  private_service_connection {
    name                           = "${var.app_name}-cache-pe"
    private_connection_resource_id = azurerm_managed_redis.treasure.id
    subresource_names              = ["redisEnterprise"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name = "default"
    private_dns_zone_ids = [
      azurerm_private_dns_zone.redis.id,
    ]
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
  name                      = var.app_name
  resource_group_name       = azurerm_resource_group.treasure.name
  location                  = azurerm_resource_group.treasure.location
  service_plan_id           = azurerm_service_plan.treasure.id
  virtual_network_subnet_id = azurerm_subnet.treasure.id

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
    CACHE_URL          = azurerm_managed_redis.treasure.hostname
    WEBAPP_CLIENT_ID   = azurerm_user_assigned_identity.webapp.client_id
  }

  https_only = true

  site_config {
    always_on           = false
    minimum_tls_version = "1.3"
    ftps_state          = "Disabled"
    http2_enabled       = true
    app_command_line    = "daphne -b 0.0.0.0 treasure.asgi:application"
    application_stack {
      python_version = "3.13"
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.webapp.id]
  }
}
