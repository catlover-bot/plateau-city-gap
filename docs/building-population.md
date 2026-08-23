# Building-level population design (Priority 2)

This calculation is not part of Priority 1 and no building population output is currently
presented as observed data.

The planned model allocates each 500 m mesh's published population and 65+ population only among
eligible residential PLATEAU buildings. Candidate weights, in evidence order, are official floor
area, footprint times official storeys, official footprint, then mesh fallback when coverage or
attributes are insufficient. The exact usage codelist and attribute availability must first be
verified against the ingested Maizuru data.

For building `b` in mesh `m`:

```text
estimated_population_b = population_m * weight_b / sum(weight in m)
```

The same rule applies independently to the 65+ total. Required validation is conservation within
a floating tolerance for every mesh, explicit coverage ratio, residential-building count,
floor-area completeness, and a `population_resolution` of either `building_estimate` or
`mesh_fallback`. Zero-coverage meshes retain the published mesh value; the system must never
fabricate buildings to absorb it.

These are statistical allocations, not resident, household or address records. UI/API fields
must use `estimated_` names and show the source mesh, weight, method, data versions and fallback
state.
