# ADR-0010: OpenStreetMap (Overpass) as the first automatic discovery source

**Context.** The owner does not want to enter companies by hand: the Discovery agent must
find businesses itself (CLAUDE.md §8.2). Google Places needs a billing account, 2GIS needs an
agreement, scraping directories is excluded (§4.6). ADR-0007 asks for minimal running cost.

**Decision.** The default `SEARCH_PROVIDER=osm` queries the public Overpass API for named
businesses (shops, cafes, hotels, clinics, training centres, offices, car services, beauty,
workshops) inside a city area of UZ/KZ/KG/TJ. Data is ODbL; attribution "© OpenStreetMap
contributors" is shown wherever such data appears. Requests identify SMY Agent in the
User-Agent, are few (one query per city × category, re-run every 7 days, at most a few per
cron run) and stay within Overpass fair use. Six UZ cities are seeded (Denov, Termiz,
Toshkent, Samarqand, Buxoro, Qarshi); the owner can change them at `/discovery`.
Paid providers (Google Places, 2GIS) plug into the same `SearchProvider` interface later.

**Consequences.** Free and lawful, zero setup. Coverage in smaller towns depends on OSM
mappers and is weaker than 2GIS; many entries lack a website — which is itself the most
common opportunity signal for M6. The host must reach `overpass-api.de` (checked by
`scripts/check_environment.py`); this sandbox cannot, so the adapter is tested against
recorded response shapes with mocked HTTP.
