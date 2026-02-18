(function () {
  "use strict";

  window.gm_authFailure = function () {
    if (
      confirm(
        "Google Maps doesn't seem to be working right now. Do you want to try the alternative map instead?"
      )
    ) {
      const params = new URLSearchParams(window.location.search);
      const lvl = params.get("lvl");
      let href = "/alt-map";

      if (lvl !== null) {
        href += "?lvl=" + lvl;
      }

      window.location.href = href;
    }
  };

  let marker = null;
  let map;
  let searchButton;
  let autocomplete;

  function createOrMoveMarker(latLng) {
    if (marker === null) {
      marker = new google.maps.Marker({
        map: map,
        position: latLng,
      });
    } else {
      marker.setPosition(latLng);
    }

    searchButton.disabled = false;
    searchButton.classList.remove("disabled");
  }

  function setMarkerToResult() {
    const place = autocomplete.getPlace();

    if (place.geometry) {
      const bounds = new google.maps.LatLngBounds();

      createOrMoveMarker(place.geometry.location);

      if (place.geometry.viewport) {
        bounds.union(place.geometry.viewport);
      } else {
        bounds.extend(place.geometry.location);
      }
      map.fitBounds(bounds);
    }
  }

  function moveToPlace(event) {
    if (event.latLng !== null) {
      createOrMoveMarker(event.latLng);
    }
  }

  function searchHere() {
    if (marker !== null && marker.getPosition() !== null) {
      const searchPos = marker.getPosition();
      const params = new URLSearchParams({
        lat: searchPos.lat(),
        long: searchPos.lng(),
      });
      const lvl = new URL(window.location).searchParams.get("lvl");

      if (lvl !== null) {
        params.set("lvl", lvl);
      }

      window.location.href = "/do-search?" + params;
    }
  }

  // Exposed as global for Google Maps API callback
  window.initAutocomplete = function () {
    map = new google.maps.Map(document.getElementById("map"), {
      center: { lat: 20, lng: 8 },
      zoom: 2,
      streetViewControl: false,
      rotateControl: false,
      zoomControl: true,
      zoomControlOptions: {
        position: google.maps.ControlPosition.RIGHT_CENTER,
      },
      fullscreenControl: true,
      fullscreenControlOptions: {
        position: google.maps.ControlPosition.RIGHT_BOTTOM,
      },
      mapTypeControl: false,
    });

    const input = document.getElementById("autocomplete");

    autocomplete = new google.maps.places.Autocomplete(input);
    autocomplete.setOptions({ fields: ["geometry"] });
    autocomplete.addListener("place_changed", setMarkerToResult);

    map.controls[google.maps.ControlPosition.TOP_CENTER].push(input);

    searchButton = document.getElementById("search-button");
    searchButton.classList.add("disabled");
    searchButton.disabled = true;
    searchButton.addEventListener("click", searchHere);

    map.addListener("click", moveToPlace);
  };
})();
