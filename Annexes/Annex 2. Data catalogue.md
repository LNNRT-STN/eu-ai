# **Data catalogue**

To open the data, see the **Setup Guide** document. This document describes what is in the
data and what each dataset can and cannot tell you.

## **1. About this data**

The challenge data holds four core datasets about the July 2021 floods in Belgium,
Germany and the Netherlands:


1. **Where it flooded:** Copernicus EMS Rapid Mapping (observed flood extent from
satellite images)
2. **What the models expected:** EFAS river flood hazard maps
3. **What buildings were there:** GHS-OBAT
4. **Who lived there:** GHS-POP

They were chosen because they fit together. All of them come from European public
sources (JRC and Copernicus) and are free to use with credit. You are welcome to add other
public datasets, such as [OpenStreetMap,](https://www.openstreetmap.org/#map=19/50.864801/4.395223) [Eurostat, or even](https://ec.europa.eu/eurostat/web/products-eurostat-news/w/ddn-20251119-1) [Groundsource.](https://research.google/blog/introducing-groundsource-turning-news-reports-into-data-with-gemini/)

## **2. Where the data lives**

Everything is in one Google Cloud Storage bucket:


  - **Path (for code):** gs://datasets_challenge/working_data

  - **Browser view:**
[https://console.cloud.google.com/storage/browser/datasets_challenge/working_data](https://console.cloud.google.com/storage/browser/datasets_challenge/working_data)
(the Google Cloud Console may ask you to sign in with a Google account)
The bucket is **read-only** : you read the data directly from the cloud, and nobody can
change or delete the files.


working_data/
── cems-efas/  EFAS flood hazard: 3 GeoTIFFs (0.95 GB)
── ems_be/   Rapid Mapping, Belgium: 4 products (0.39 GB)
── ems_de/   Rapid Mapping, Germany: 22 products (0.54 GB)
── ems_nl/   Rapid Mapping, Netherlands: 1 product (0.06 GB)
── ghs_pop/   Population rasters, 2020 and 2025 (1.03 GB)
── obat_be/   Buildings, Belgium (1.44 GB)
── obat_de/   Buildings, Germany (8.58 GB)
── obat_nl/   Buildings, Netherlands (2.23 GB)

Folders ending in _be, _de and _nl are the same dataset split by country. The total size is
about 15 GB.


1


## **3. Data catalogue**

















|Google Cloud<br>folder|Dataset|What it is|Answers|Data type|Format and<br>size|
|---|---|---|---|---|---|
|ems_be,<br>ems_de,<br>ems_nl<br>|Copernicus EMS<br>Rapid Mapping<br>(activations<br>EMSR518 BE,<br>EMSR517 DE,<br>EMSR520 NL)|Flood maps<br>drawn by<br>analysts from<br>satellite images<br>during the 2021<br>floods: where the<br>water was and<br>which buildings<br>were hit.|Where was the<br>water, as seen<br>by satellite?|Vector: polygons,<br>points, lines<br>drawn by<br>analysts from<br>satellite images|One folder per<br>product, with<br>shapefiles plus<br>JSON, KMZ and<br>XML copies: BE 4<br>products (0.39<br>GB), DE 22 (0.54<br>GB), NL 1 (0.06<br>GB)|
|cems-efas|EFAS river flood<br>hazard maps for<br>Europe|Model-based<br>maps of how<br>deep the water<br>gets in a 10-<br>year, 100-year<br>and 500-year<br>river flood, for<br>the whole of<br>Europe.|Where does a<br>model expect<br>water in a 10-,<br>100-, 500-year<br>river flood?|Raster (water<br>depth)|3 GeoTIFFs, 0.95<br>GB in total|
|obat_be,<br>obat_de, obat_nl <br>|GHS-OBAT<br>R2024A|One record per<br>building:<br>location, use<br>(residential or<br>not) and, where<br>known, height<br>and construction<br>period. Reference<br>year 2020.|Which buildings<br>were there, and<br>are they<br>residential?|Vector (one point<br>per building),<br>reference year<br>2020. Fields:<br>location, use,<br>and where<br>known height<br>and construction<br>period|One GeoPackage<br>plus a PDF per<br>country: BE 1.44<br>GB, NL 2.23 GB,<br>DE 8.58 GB|
|ghs_pop|GHS-POP<br>R2023A|Estimated<br>number of<br>residents per<br>grid cell, for the<br>years 2020 and<br>2025 (projection)|How many<br>residents per<br>grid cell?|Raster (people<br>per cell)|2 GeoTIFFs of<br>about 0.5 GB<br>(2020 and<br>2025), each with<br>an overview file<br>(.ovr), a PDF and<br>an Excel file|


2








## **4. Dataset fact sheets**

**EMS Rapid Mapping (ems_be, ems_de, ems_nl)**


[Link: https://mapping.emergency.copernicus.eu/](https://mapping.emergency.copernicus.eu/)


   - Analysts drew flood maps from satellite images during the event. Activations:
EMSR517 Germany (activated 13 July 2021), EMSR518 Belgium (14 July),
EMSR520 Netherlands (15 July).

   - It is the only observation of the real flood in this challenge, not a model.

   - Each map is a snapshot of the water at the moment the satellite passed, not the
peak.

   - Coverage is partial: analysts mapped only the areas that authorities asked for,
called AOIs (areas of interest). Germany has many AOIs, Belgium two, the
Netherlands one. Outside the AOIs, "not flooded" means "not mapped".

   - Product type: the files we provide are delineations (DEL): flood extent only, no
damage grades. Some areas may also contain grading products (GRA) with damage
levels. A building counts as "hit" only because you overlaid it on the flood extent.


**EFAS flood hazard maps (cems-efas)**


[Link: https://data.jrc.ec.europa.eu/collection/id-0054](https://data.jrc.ec.europa.eu/collection/id-0054)


   - Model-based water depth for a 10-, 100- and 500-year river flood, for all of
Europe.

   - Return periods: a 100-year flood has a 1% chance of happening in any given year
(10-year: 10%, 500-year: 0.2%).

   - Small rivers are left out. The model excludes rivers with an upstream catchment
below 500 km². Empty cells therefore mean not modelled.

   - The 500-year map is the ceiling, and the hydrological model was run on 1990 to
2016 data. The 2021 flood went beyond that in places.


**GHS-OBAT buildings (obat_be, obat_de, obat_nl)**


[Link: https://data.jrc.ec.europa.eu/dataset/f41a22f1-5741-4c41-86eb-6384654f6927](https://data.jrc.ec.europa.eu/dataset/f41a22f1-5741-4c41-86eb-6384654f6927)


   - One record per building, as a single point. Fields: location, use (residential or not)
and, where known, height and construction period. Reference year 2020.

   - Attributes: how "residential" is coded, and what the height and period codes mean.

   - Points, not footprints: you cannot measure building area, and buildings near a flood
edge can fall in or out depending on the point position.

   - Belgium is undercounted: in our tests OBAT returned noticeably fewer buildings
inside the Belgian flood areas than expected.

   - Not every record is a home. Non-residential buildings are included.


**GHS-POP population (ghs_pop)**


[Link: https://data.jrc.ec.europa.eu/dataset/2ff68a52-5b5b-4a22-8f40-c41da8332cfe](https://data.jrc.ec.europa.eu/dataset/2ff68a52-5b5b-4a22-8f40-c41da8332cfe)


3


- Estimated residents per grid cell. The file is a single global raster in EPSG:4326 at
30 arc-seconds.

- Year: use E2020 for the 2021 event. E2025 is a projection.

- Residents only: commuters and visitors are missing. There is no age or status
information.

- Not independent of OBAT: GHS-POP is modelled from census data and built-up
area, so population and building counts are related by construction.

- Partly flooded cells: a flood polygon rarely matches cell borders. Weight each cell by
the share of its area that is flooded, or say clearly that you did not.


4


