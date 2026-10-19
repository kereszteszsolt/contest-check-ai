# ContestCheck AI branding

[`branding.json`](branding.json) follows the TypeNudge display-branding contract. Edit project metadata here. It contains no credentials or runtime provider configuration.

The field order below is shared by every repository using this branding structure. Keep the JSON keys in exactly this order and preserve all field values when reordering them.

| Field | Meaning |
| --- | --- |
| `appName` | Display name |
| `appTagline` | Project tagline |
| `appDescription` | Project description |
| `appWebsite` | Project website; empty when none is configured |
| `appGithubUrl` | Project repository |
| `appFavicon` | Optional local favicon |
| `appIcon` | Optional local project mark |
| `appPoster` | Optional local project poster |
| `authorName` | Author display name |
| `authorWebsite` | Author website |
| `authorWebsiteLanguages` | Ordered language codes for the author website |
| `authorGithub` | Author GitHub profile |
| `authorWaysToSupportUrl` | General ways to support the author |
| `authorBuyMeACoffeeUrl` | Direct Buy Me a Coffee link |
| `supportRemarkText` | Voluntary-support notice |

Asset paths are relative to this `brand/` directory and must stay inside `assets/`. Empty paths mean no image. These are source paths, not public URLs: consumers must package or map them to their own public base. Do not fetch remote artwork or resolve arbitrary filesystem paths.

The SVG and PNG posters are unchanged copies of `kereszteszsolt/project-cards/contest-check-ai-poster.*` from the profile repository. `appPoster` selects the vector version; the PNG is the social-preview alternative. `assets/contest-check-ai-icon.svg` adapts the poster's code sheet, coral stamp and mint accepted check into a compact vector app icon/favicon. Preserve the original artwork when adding variants.

This directory is the project branding and artwork catalog. `contest_check.branding` loads these display fields for the navbar, favicon, sidebar attribution and native Streamlit About dialog. The sidebar starts expanded; its existing workspace menu and native collapse control remain available. Copyright/license share one line, with the author website below. About follows the shared app pattern: original poster, centered description, website/source/profile links, coffee/support links, voluntary-support note and centered copyright/license. Links include keyboard-accessible descriptions and full URLs.

The wheel includes the JSON and original assets through Hatch's `force-include` mapping; development uses this source directory directly. SVG artwork is embedded as local data URLs, without remote image requests or generated copies. Docker's allowlisted context includes only the required brand metadata/artwork and packaged styles. No credentials belong in this catalog.

No extra JSON fields are needed for this project.

License identifiers and URLs are not part of the branding contract. The legal source of truth remains the root `LICENSE` and existing SPDX notices; branding edits must not rewrite those or rename stable storage/package identifiers.
