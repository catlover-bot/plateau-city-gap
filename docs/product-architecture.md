# CITY GAP Product System 2.0 architecture

## Product boundary

Product System 2.0 is a presentation and interaction refactor over the existing CITY GAP analysis platform. It does not recompute, rename, or replace the real analysis artifacts, PLATEAU-native pipeline, PostGIS platform, validation evidence, temporal validation, resilience calculations, privacy rules, or municipal workflow contracts.

The root `App.tsx` changed from a 729-line state coordinator to a six-line provider/entrypoint. Responsibilities now follow user intent:

```text
SpatialProvider
  └─ ProductApp / shared shell
      ├─ navigation: discover · detail · try · validate · operate
      ├─ map: MapLibre 2D or lazy Cesium 3D
      ├─ Context Inspector
      └─ feature workspaces
          ├─ discovery
          ├─ detail
          ├─ scenario + resilience
          ├─ validation
          └─ field / municipal operation
```

## State ownership

`state/spatial` owns city, urban state, task, selection, scenario, validation sample, renderer, map state, layer preset, primary layer, viewport, Inspector state, and demo state. A single reducer provides explicit transitions. Feature components request actions; they do not own an independent map or duplicate geographic selection.

The unified selection contract covers `mesh`, `building`, `road`, `facility`, `scenario_site`, `validation_sample`, and `temporal_change`. Task changes preserve selection. City changes clear an incompatible selection and reset to the documented city viewport.

## URL state and compatibility

The URL serializes city, workspace/task, urban state, selected entity, scenario, validation sample, map mode, primary layer, and viewport. The parser retains compatibility with the prior `demo`, `workspace`, `validation`, `futures`, and `admin` workspace keys. Copying the URL therefore carries the spatial context, not merely the route.

## Loading boundary

Maizuru screening data is the initial product payload. Fujisawa, Validation, Urban Futures, Municipal data, and Cesium are loaded only when the corresponding task requires them. The browser QA gate asserts that the 2D overview requests no Cesium module, worker, or asset. The production build keeps Cesium in a separate chunk.

## Existing platform preservation

Existing feature components and their unit tests remain in place so Municipal, Validation, Urban Futures, Evidence, and field contracts continue to be regression-tested. The new shell reads their public artifacts through the same `lib/data.ts` loaders. No analysis output was changed by this frontend refactor.
