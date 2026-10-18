# Attribution: terrain pack "Osprey Town"

This terrain pack is built from open research datasets and published specifications, in a
fictional scenario. "Osprey Town" is a fictional name. The pack does not represent any real
site, installation or operational situation.

## Elevation

NASA Shuttle Radar Topography Mission, SRTM GL1 (1 arc-second) Global, version 003.
NASA JPL (2013). NASA Shuttle Radar Topography Mission Global 1 arc second [Data set].
NASA EOSDIS Land Processes DAAC. https://doi.org/10.5067/MEaSUREs/SRTM/SRTMGL1.003
The data are shared without restriction; citation is requested. The heightmap in this pack is a
bilinear resample of that tile, with voids filled by interpolation.

## Map features

Building outlines, land cover, roads and trees are derived from OpenStreetMap data.

© OpenStreetMap contributors. https://www.openstreetmap.org/copyright

OpenStreetMap data is available under the Open Database License (ODbL) 1.0,
https://opendatacommons.org/licenses/odbl/1-0/.

This pack is a Derivative Database of OpenStreetMap data and is offered under the ODbL 1.0.
Anyone who uses, redistributes or adapts the pack's data files (buildings.json, vegetation.json,
the landcover texture in terrain.glb and the building shapes in buildings.glb) must keep this
notice, credit OpenStreetMap contributors and share adaptations under the same licence.
Building heights that were not tagged in OpenStreetMap are defaults chosen by the bake tool and
are counted in manifest.json; they are not surveyed values.

## Bake

Produced by the terrain-bake tool, version 1.0.0, from areas.json#osprey-town. The bake is
reproducible: the same inputs give byte-identical files, listed with SHA-256 in manifest.json.
