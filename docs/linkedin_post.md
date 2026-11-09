# LinkedIn post draft

> Draft for the author to edit and post. Every number comes from `fleetsim bench` (README results table).

---

Two weeks, ~8 hours, $0 of hardware: v0.1 of **fleetsim**, a simulated Amazon-style fulfillment fleet.

Robots fetch storage pods, carry them to pick stations and put them back. The warehouse is a real benchmark map from the League of Robot Runners. What's in v0.1:

🔹 Motion planning: space-time A* with prioritized planning and a reservation table. 0 collisions across 2.7 M robot-seconds, verified by an independent collision checker (which also runs in the CI test suite).
🔹 Task allocation: greedy nearest-robot vs Hungarian assignment (scipy linear_sum_assignment) re-solved every 5 s. Under a backlog, Hungarian completes +16-20% more tasks per hour (1,619 -> 1,892 tasks/h with 100 robots) and halves the queue. Without a backlog the two are the same, and part of the gain probably comes from *which* order gets picked, not just optimal matching. That's the next experiment.
🔹 Analytics: every robot-second logged to SQLite/Parquet, KPIs in plain SQL (throughput, utilization, congestion delay, censored order wait, planner runtime). Same toolkit I use in bank credit-risk work, applied to a fleet.

Next: port the planner to C++ and wrap it in ROS 2 Jazzy nodes, then Gazebo/Isaac visualisation, a perception pick station and learned dispatch policies.

Built with AI coding agents (Claude Code); the README logs which parts.

Code: https://github.com/zakcination/fleetsim

#robotics #MAPF #operationsresearch #ROS2 #python #warehouseautomation
