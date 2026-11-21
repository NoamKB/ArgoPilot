---
type: llm
focus: trace
weight: 1
---

PATCH that renames a plot to another plot's name on the same farm returns 409 with body exactly {"detail": "Plot name already exists on this farm"} and leaves the plot unchanged
