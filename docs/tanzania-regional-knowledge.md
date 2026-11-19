# Tanzania regional knowledge guide

## Purpose and boundary

SafariSmart recognizes all 31 official Tanzanian regions for tourism discovery. This guide is read-only application knowledge, separate from the PostgreSQL `destinations` catalog.

- A recognized region is **not** proof of live availability, inventory, an operator relationship, or a bookable product.
- Only the five active catalog destinations can return a `booking_destination_id` or a booking-form link.
- Regional facts never include invented prices, hotel availability, opening hours, transport times, or partnerships.
- When attraction detail has not been reviewed, the concierge gives only the verified administrative context and says that detail is limited.

The code lives in `backend/app/knowledge/tanzania_regions.py`. Each profile records its official name, slug, statistical zone, conservative aliases, selected highlights, source URLs, and last verification date. Adding a region or highlight does not require changing the conversational resolver.

## Official region set

The dataset was checked on **2026-11-19** against Tanzania's National Bureau of Statistics (NBS). The 31 regions comprise 26 on the mainland and five in Zanzibar:

- Mainland: Arusha, Dar es Salaam, Dodoma, Geita, Iringa, Kagera, Katavi, Kigoma, Kilimanjaro, Lindi, Manyara, Mara, Mbeya, Morogoro, Mtwara, Mwanza, Njombe, Pwani, Rukwa, Ruvuma, Shinyanga, Simiyu, Singida, Songwe, Tabora, and Tanga.
- Zanzibar: Kaskazini Pemba, Kusini Pemba, Kaskazini Unguja, Kusini Unguja, and Mjini Magharibi.

Administrative and zone sources:

- [NBS 2022 Population and Housing Census administrative report](https://www.nbs.go.tz/nbs/takwimu/Census2022/Administrative_units_Population_Distribution_Report_Tanzania_volume1a.pdf)
- [NBS 2022 Tanzania Demographic and Health Survey summary](https://www.nbs.go.tz/uploads/statistics/documents/en-1705490101-Tanzania_DHS-MIS_2022_Summary_Report_English_and_Swahili.pdf)
- [Tanzania Government mainland regional directory](https://www.tanzania.go.tz/directories/local-government)

## Reviewed tourism highlights

The initial release intentionally keeps the attraction layer small. These are discovery examples, not exhaustive regional itineraries:

| Region | Reviewed highlight | Primary source |
| --- | --- | --- |
| Mwanza | Saanane Island National Park | [Tanzania National Parks](https://www.tanzaniaparks.go.tz/nationalparks/saanane) |
| Arusha | Arusha National Park | [Tanzania National Parks](https://www.tanzaniaparks.go.tz/nationalparks/arusha) |
| Kilimanjaro | Kilimanjaro National Park | [Tanzania National Parks](https://www.tanzaniaparks.go.tz/nationalparks/kilimanjaro) |
| Dar es Salaam | Dar es Salaam Marine Reserves | [Marine Parks and Reserves Unit](https://www.marineparks.go.tz/index.php/pages/marine-reserves) |
| Dodoma | Kondoa Rock-Art Sites | [UNESCO World Heritage Centre](https://whc.unesco.org/en/list/1183/) |
| Mbeya | Lake Ngozi and Mount Rungwe | [Mbeya Regional Secretariat socio-economic profile](https://mbeya.go.tz/storage/app/uploads/public/5df/885/0ff/5df8850ff1e51431088709.pdf) |
| Morogoro | Mikumi National Park | [Tanzania National Parks](https://www.tanzaniaparks.go.tz/nationalparks/mikumi) |
| Tanga | Tanga Coelacanth Marine Park | [Marine Parks and Reserves Unit](https://www.marineparks.go.tz/pages/marine-history) |
| Iringa | Ruaha National Park | [Tanzania National Parks](https://www.tanzaniaparks.go.tz/nationalparks/ruaha) |
| Kigoma | Gombe National Park | [Tanzania National Parks](https://www.tanzaniaparks.go.tz/nationalparks/gombe) |
| Mjini Magharibi | Stone Town of Zanzibar | [UNESCO World Heritage Centre](https://whc.unesco.org/en/list/173) |

## Safe extension checklist

Before adding or expanding a profile:

1. Use an official Tanzanian authority, the attraction's public authority, UNESCO, or another clearly accountable primary source.
2. Record the direct source URL and update `verified_on`.
3. Summarize stable characteristics only; omit live operational claims unless a maintained integration exists.
4. Add both concise English and Kiswahili wording plus bounded activity themes.
5. Add exact-name, alias, and false-positive tests.
6. Confirm the profile remains outside the database catalog unless a separate, explicitly authorized catalog-and-booking milestone is completed.

The resolver accepts curated aliases and conservative single-character misspellings for single-word official names. It deliberately avoids broad fuzzy or model-based place guessing.
