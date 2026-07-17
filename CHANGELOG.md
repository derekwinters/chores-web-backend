# Changelog

## [2.5.0](https://github.com/derekwinters/chores-web-backend/compare/v2.4.0...v2.5.0) (2026-07-16)


### Features

* add admin endpoint for one-time point awards ([#44](https://github.com/derekwinters/chores-web-backend/issues/44)) ([f3055de](https://github.com/derekwinters/chores-web-backend/commit/f3055de0a5f6443a9c0585ed26f58ec057533742))
* allow zero-point chores as task reminders ([#46](https://github.com/derekwinters/chores-web-backend/issues/46)) ([8bbb686](https://github.com/derekwinters/chores-web-backend/commit/8bbb686489da93d3c9fedaf041d926909643841b))
* expose backend and API version on /status/ ([#47](https://github.com/derekwinters/chores-web-backend/issues/47)) ([c9f87c7](https://github.com/derekwinters/chores-web-backend/commit/c9f87c71edc97a816291c4647807808193572bb7))


### Bug Fixes

* make update check fire reliably and target split release repos ([#51](https://github.com/derekwinters/chores-web-backend/issues/51)) ([79e0476](https://github.com/derekwinters/chores-web-backend/commit/79e0476b2915e4a9c0e5483bff939f3d4c53e359))
* replace starlette-prometheus with prometheus-fastapi-instrumentator ([#48](https://github.com/derekwinters/chores-web-backend/issues/48)) ([8afe0aa](https://github.com/derekwinters/chores-web-backend/commit/8afe0aa57b94d2e98411dfb4945fed399eba020c))

## [2.4.0](https://github.com/derekwinters/chores-web-backend/compare/v2.3.0...v2.4.0) (2026-07-14)


### Features

* notification domain model, generation, and stale dismissal ([#41](https://github.com/derekwinters/chores-web-backend/issues/41)) ([f254bb7](https://github.com/derekwinters/chores-web-backend/commit/f254bb7c40543d2764dd3cc85f048953e4447a73))
* notifications API — list, acknowledge, preferences ([#43](https://github.com/derekwinters/chores-web-backend/issues/43)) ([5f8ba0d](https://github.com/derekwinters/chores-web-backend/commit/5f8ba0d820a8f662a4079ee278364e232cb6887b))

## [2.3.0](https://github.com/derekwinters/chores-web-backend/compare/v2.2.0...v2.3.0) (2026-07-12)


### Features

* retroactively document cb19143 for release-please ([98953ec](https://github.com/derekwinters/chores-web-backend/commit/98953ec2a7ee8994e010f3d88a3cda546f38391e))


### Documentation

* require conventional commits and agent-delegated commit work ([77c026e](https://github.com/derekwinters/chores-web-backend/commit/77c026e4d625676432cf717a05ff7bb6dcc669d5))

## [2.2.0](https://github.com/derekwinters/chores-web-backend/compare/v2.1.0...v2.2.0) (2026-07-10)


### Features

* source built-in theme palettes from the design-tokens artifact ([#23](https://github.com/derekwinters/chores-web-backend/issues/23)) ([b3652f1](https://github.com/derekwinters/chores-web-backend/commit/b3652f152de419d5a2fe16f9a3247b85b211dee3))


### Bug Fixes

* track renamed npm package @derekwinters/design-tokens ([#24](https://github.com/derekwinters/chores-web-backend/issues/24)) ([983fd89](https://github.com/derekwinters/chores-web-backend/commit/983fd89c139a0bdd25fb825d41e94b286cf76950))


### CI/CD

* add dependabot configuration ([#2](https://github.com/derekwinters/chores-web-backend/issues/2)) ([57ed61c](https://github.com/derekwinters/chores-web-backend/commit/57ed61c4734988003981647d893ed37ce6e3d930))
* fix upgrade-regression job — old-backend env and seed.py /v1 paths ([#26](https://github.com/derekwinters/chores-web-backend/issues/26)) ([86f3206](https://github.com/derekwinters/chores-web-backend/commit/86f320620d8a33a63183d03861d142e93938f8d7)), closes [#25](https://github.com/derekwinters/chores-web-backend/issues/25)
* group dependabot updates and add 14-day cooldown ([#19](https://github.com/derekwinters/chores-web-backend/issues/19)) ([76f1c76](https://github.com/derekwinters/chores-web-backend/commit/76f1c768ef6f778501a984238de350ccefc270ea))

## [2.1.0](https://github.com/derekwinters/chores-web-backend/compare/v2.0.1...v2.1.0) (2026-07-09)


### Features

* bootstrap standalone backend repository ([ab93905](https://github.com/derekwinters/chores-web-backend/commit/ab93905723e10641b687dc537506d3c8b939e36b))


### CI/CD

* grant packages permission to docker-build job ([4cbf6ca](https://github.com/derekwinters/chores-web-backend/commit/4cbf6ca5b7b4db1c7cd1c04478e7c0794997dbcd))
