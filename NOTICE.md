# Data Source & Attribution

This integration retrieves shared-mobility data at runtime from the official **sharedmobility.ch** platform, operated by the Swiss Federal Office of Energy (BFE / SFOE). It uses the public sharedmobility.ch REST API (`api.sharedmobility.ch`), which serves the same data as the platform's GBFS feed.

The dataset is published as Open Data on [opendata.swiss](https://opendata.swiss/en/dataset/standorte-und-verfugbarkeit-von-shared-mobility-angeboten) under the **"Open use. Must provide the source."** terms: free use for non-commercial and commercial purposes, the source must be cited.

**Required attribution:** *sharedmobility.ch (Swiss Federal Office of Energy SFOE)*

This integration fulfills that requirement by setting the `attribution` attribute (`"Data: sharedmobility.ch (Swiss Federal Office of Energy SFOE)"`) on every entity it creates, which Home Assistant surfaces in the entity's "More Info" dialog. If you build dashboards, automations, or republish this data elsewhere, please keep that attribution visible or add your own equivalent notice.

## Scope

This integration is unofficial and not affiliated with, endorsed by, or supported by the BFE / SFOE, sharedmobility.ch, or any of the shared-mobility providers whose vehicles appear in the data. It only reads the published Open Data.

Official documentation: https://github.com/SFOE/sharedmobility
