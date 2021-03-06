Version 0.14 - dev
------------------

- Release notes: https://ezdxf.mozman.at/release-v0-14.html
- CHANGE: `linspace()` uses Decimal() for precise calculations, but still returns float
- NEW: `TraceBuilder()` a render tool to generate quadrilaterals (TRACE, SOLID or 3DFACE) 
  from LWPOLYLINE or 2D POLYLINE with width information.
- NEW: `Arc.construction_tool()` returns the 2D `ConstructionArc()`
- NEW: `Arc.apply_construction_tool()` apply parameters from `ConstructionArc()`
- NEW: `LWPolyline.has_width` property is ``True`` if any width attribute is set
- NEW: `Polyline.has_width` property is ``True`` if any width attribute is set
- NEW: `addons.drawing.Frontend()` supports width attributes of LWPOLYLINE and 2D POLYLINE entities