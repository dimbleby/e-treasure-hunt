(function () {
  "use strict";

  const map = L.map("map", {
    center: [20, 8],
    zoom: 3,
  });

  let latlng = null;
  const searchButton = document.getElementById("search-button");
  searchButton.disabled = true;
  searchButton.classList.add("disabled");

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      "&copy; <a href='https://osm.org/copyright'>OpenStreetMap</a> contributors",
  }).addTo(map);

  const searchControl = new L.esri.Geocoding.geosearch({
    providers: [
      L.esri.Geocoding.arcgisOnlineProvider({
        apikey: api_key,
      }),
    ],
    placeholder: "Begin typing for suggestions",
    useMapBounds: false,
  }).addTo(map);

  map.zoomControl.setPosition("topright");

  const results = new L.LayerGroup().addTo(map);
  L.control.scale().addTo(map);

  function enableSearch(ll) {
    results.clearLayers();
    latlng = ll;
    results.addLayer(L.marker(latlng, { draggable: true }));
    searchButton.disabled = false;
    searchButton.classList.remove("disabled");
  }

  searchControl.on("results", function (data) {
    enableSearch(data.results[0].latlng);
  });

  map.on("click", function (e) {
    enableSearch(e.latlng);
  });

  searchButton.addEventListener("click", function () {
    if (latlng !== null) {
      const params = new URLSearchParams({
        lat: latlng.lat,
        long: latlng.lng,
      });
      const lvl = new URL(window.location).searchParams.get("lvl");

      if (lvl !== null) {
        params.set("lvl", lvl);
      }

      window.location.href = "/do-search?" + params;
    }
  });
})();
