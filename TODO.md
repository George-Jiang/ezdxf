TODO
====

Add-ons
-------

- DWG loader (work in progress)
- Simple SVG exporter
- drawing
    - LEADER
    - ACAD_TABLE
    - MLEADER ???
    - MLINE ???
    - render POINT symbols
    - resolve fonts and pass them to `draw_text()`, 
      `get_font_measurements()` and `get_text_line_width()`
    - render proxy graphic, class `ProxyGraphic()` is already 
      implemented but not tested with real world data.

Render Tools
------------

- `Leader.virtual_entities()`
- `ACADTable.virtual_entities()`
- `MLeader.virtual_entities()` ???
- `MLine.virtual_entities()` ???
- LWPOLYLINE and 2D POLYLINE the `virtual_entities(dxftype='ARC')` method
  could return bulges as ARC, ELLIPSE or SPLINE entities
  

DXF Entities
------------

- DIMENSION rendering
    - angular dim
    - angular 3 point dim
    - ordinate dim
    - arc dim
- MLEADER
- MLINE
- FIELD
- ACAD_TABLE

DXF Audit & Repair
------------------

- check ownership
    - DXF objects in OBJECTS section
    - DXF Entities in a layout (model space, paper space, block)
- check DIMENSION
    - dimstyle exist
    - arrows exist
    - text style exist
- check TEXT, MTEXT
    - text style exist
- check required DXF attributes:
    - R12: layer; repair: set to '0' (in ezdxf defaults to '0')
    - R2000+: layer, owner?, handle?
- VERTEX on same layer as POLYLINE; repair: set VERTEX layer to POLYLINE layer
- find unreferenced objects:
    - DICTIONARY e.g. orphaned extension dicts; repair: delete
- find unused BLOCK definitions: has no corresponding INSERT; repair: delete
    - EXCEPTION: layout blocks
    - EXCEPTION: anonymous blocks without explicit INSERT like DIMENSION geometry

Cython Code
-----------

- optional for install, testing and development
- profiling required!!!
- optimized Vec2(), Vector() and Matrix44() classes
- optimized math & construction tools
- optimized tag loader
