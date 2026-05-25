# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] - 2026-05-25

### Fixed
- Add `issue_tracker` to the manifest so HACS validation passes.

## [0.1.3] - 2026-05-25

### Added
- GitHub Actions: `pytest` on every push/PR, plus `hassfest` and HACS validation.
- Contributing guide, issue/PR templates, and README badges.

### Changed
- Device info now splits the firmware string into separate fields: the console is
  shown in the model (e.g. `BlueRetro (Playstation)`), with `sw_version` and
  `hw_version` populated from it.

## [0.1.2] - 2026-05-25

### Added
- Portuguese (pt-BR, pt) and Spanish (es) translations.

## [0.1.1] - 2026-05-25

### Added
- Brand icon and logo served locally from `custom_components/blueretro/brand/`
  (Home Assistant 2026.3+); set `codeowners`.

## [0.1.0] - 2026-05-25

### Added
- Initial release: Bluetooth discovery + config flow, polling coordinator, and
  sensor / binary_sensor / button platforms for the BlueRetro adapter, backed by
  the `blueretro-ble` library.

[Unreleased]: https://github.com/hudsonbrendon/blueretro-homeassistant/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/hudsonbrendon/blueretro-homeassistant/releases/tag/v0.1.4
[0.1.3]: https://github.com/hudsonbrendon/blueretro-homeassistant/releases/tag/v0.1.3
[0.1.2]: https://github.com/hudsonbrendon/blueretro-homeassistant/releases/tag/v0.1.2
[0.1.1]: https://github.com/hudsonbrendon/blueretro-homeassistant/releases/tag/v0.1.1
[0.1.0]: https://github.com/hudsonbrendon/blueretro-homeassistant/releases/tag/v0.1.0
