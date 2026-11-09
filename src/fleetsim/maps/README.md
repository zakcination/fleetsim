# Maps

`warehouse_long_corridor_large.map` is copied unmodified from the
[League of Robot Runners Start-Kit](https://github.com/MAPF-Competition/Start-Kit)
(`example_problems/warehouse.domain/maps/`, commit `9bc75d9`, "2026 LoRR"),
MIT-licensed. See `LICENSE.LoRR`.

fleetsim crops rows 0-71 and columns 0-98 by default (`fleetsim.grid.DEFAULT_CROP`),
which gives a 72 x 99 grid with 4,109 traversable cells, 2,920 pod slots (`S`) and 19
left-wall pick stations (`E`). Pass `crop=None` to `Grid.from_file` to use the full
140 x 500 map.
