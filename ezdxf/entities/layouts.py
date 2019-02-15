# Created: 21.03.2011
# Copyright (c) 2011-2018, Manfred Moitzi
# License: MIT License
from typing import TYPE_CHECKING, cast, Dict, Iterable, List, Union, Tuple, Any, Optional, Hashable, Sequence
from ezdxf.entitydb import EntitySpace, EntityDB
from ezdxf.graphicsfactory import GraphicsFactory
from ezdxf.entities.factory import EntityFactory
from ezdxf.lldxf.const import DXFKeyError, DXFValueError, DXFTypeError, STD_SCALES, DXFInternalEzdxfError
from ezdxf.lldxf.validator import is_valid_name
from ezdxf.query import EntityQuery
from ezdxf.groupby import groupby

if TYPE_CHECKING:
    from ezdxf.eztypes import Drawing, TagWriter, DXFDictionary, BlockRecord
    from ezdxf.eztypes import Vertex, Viewport, GeoData, SortEntitiesTable, KeyFunc
    from ezdxf.entities.dxfentity import DXFEntity

# todo DXF12: $MODEL_SPACE and $PAPER_SPACE
PAPER_SPACE = '*Paper_Space'
TMP_PAPER_SPACE_NAME = '*Paper_Space999999'


class Layouts:
    def __init__(self, doc: 'Drawing'):
        self.doc = doc
        self._layouts = {}  # type: Dict[str, Layout]
        self._dxf_layout_management_table = None  # type: DXFDictionary # key: layout name; value: layout_handle
        self._link_entities_section_into_blocks(doc)
        self._setup()

    @staticmethod
    def _link_entities_section_into_blocks(drawing: 'Drawing') -> None:
        """
        Link entity spaces from entities section into associated block layouts.

        """
        blocks = drawing.blocks
        model_space_block = blocks.get('*MODEL_SPACE')
        model_space_block.set_entity_space(drawing.entities.model_space_entities())
        active_layout_block = blocks.get('*PAPER_SPACE')
        active_layout_block.set_entity_space(drawing.entities.active_layout_entities())
        drawing.entities.clear()  # remove entities for entities section -> stored in blocks

    @property
    def dxffactory(self) -> 'EntityFactory':
        return self.doc.dxffactory

    def entitydb(self):
        return self.doc.entitydb

    def _setup(self) -> None:
        """
        Setup layout management table.

        """
        layout_table_handle = self.doc.rootdict['ACAD_LAYOUT']
        layout_table = self.entitydb[layout_table_handle]
        self._dxf_layout_management_table = cast('DXFDictionary', layout_table)
        # name ... layout name
        # handle ...  handle to DXF object Layout
        for name, handle in self._dxf_layout_management_table.items():
            layout = Layout(self.doc, handle)
            self._layouts[name] = layout

    def __len__(self) -> int:
        """
        Returns layout count.

        """
        return len(self._layouts)

    def __contains__(self, name: str) -> bool:
        """
        Returns if layout `name` exists.

        Args:
            name str: layout name

        """
        return name in self._layouts

    def __iter__(self) -> Iterable['Layout']:
        return iter(self._layouts.values())

    def modelspace(self) -> 'Layout':
        """
        Get model space layout.

        Returns:
            Layout: model space layout

        """
        return self.get('Model')

    def names(self) -> Iterable[str]:
        """
        Returns all layout names.

        Returns:
            Iterable[str]: layout names

        """
        return self._layouts.keys()

    def get(self, name: str) -> 'Layout':
        """
        Get layout by name.

        Args:
            name (str): layout name as shown in tab, e.g. ``Model`` for model space

        Returns:
            Layout: layout

        """
        if name is None:
            first_layout_name = self.names_in_taborder()[1]
            return self._layouts[first_layout_name]
        else:
            return self._layouts[name]

    def rename(self, old_name: str, new_name: str) -> None:
        """
        Rename a layout. Layout ``Model`` can not renamed and the new name of a layout must not exist.

        Args:
            old_name (str): actual layout name
            new_name (str): new layout name

        """
        if old_name == 'Model':
            raise ValueError('Can not rename model space.')
        if new_name in self._layouts:
            raise ValueError('Layout "{}" already exists.'.format(new_name))

        layout = self._layouts[old_name]
        del self._layouts[old_name]
        layout.dxf_layout.dxf.name = new_name
        self._layouts[new_name] = layout

    def names_in_taborder(self) -> List[str]:
        """
        Returns all layout names in tab order as a list of strings.

        """
        names = [(layout.dxf.taborder, name) for name, layout in self._layouts.items()]
        return [name for order, name in sorted(names)]

    def get_layout_for_entity(self, entity: 'DXFEntity') -> 'Layout':
        """
        Returns layout the `entity` resides in.

        Args:
            entity (DXFEntity): generic DXF entity

        """
        return self.get_layout_by_key(entity.dxf.owner)

    def get_layout_by_key(self, layout_key: str) -> 'Layout':
        """
        Returns a layout by its layout key.

        Args:
            layout_key (str): layout key

        """
        for layout in self._layouts.values():
            if layout_key == layout.layout_key:
                return layout
        raise DXFKeyError('Layout with key "{}" does not exist.'.format(layout_key))

    def new(self, name: str, dxfattribs: dict = None) -> 'Layout':
        """
        Create a new Layout.

        Args:
            name (str): layout name as shown in tab
            dxfattribs (dict): DXF attributes for the ``LAYOUT`` entity

        """
        if not is_valid_name(name):
            raise DXFValueError('name contains invalid characters')

        if dxfattribs is None:
            dxfattribs = {}

        if name in self._layouts:
            raise DXFValueError('Layout "{}" already exists'.format(name))

        def create_dxf_layout_entity() -> str:
            dxfattribs['name'] = name
            dxfattribs['owner'] = self._dxf_layout_management_table.dxf.handle
            dxfattribs.setdefault('taborder', len(self._layouts) + 1)
            dxfattribs['block_record'] = block_record_handle
            entity = self.doc.objects.create_new_dxf_entity('LAYOUT', dxfattribs)
            return entity.dxf.handle

        block_layout = self.doc.blocks.new_layout_block()
        block_record_handle = block_layout.block_record_handle
        block_record = block_layout.block_record
        layout_handle = create_dxf_layout_entity()
        block_record.dxf.layout = layout_handle

        # create valid layout entity
        layout = Layout(self.doc, layout_handle)

        # add layout to management tables
        self._dxf_layout_management_table[name] = layout_handle
        self._layouts[name] = layout

        return layout

    def set_active_layout(self, name: str) -> None:
        """
        Set active paper space layout.

        Args:
            name (str): layout name as shown in tab

        """
        if name == 'Model':  # reserved layout name
            raise DXFValueError('Can not set model space as active layout')
        new_active_layout = self.get(name)  # raises KeyError if no layout 'name' exists
        old_active_layout_key = self.doc.get_active_layout_key()
        if old_active_layout_key == new_active_layout.layout_key:
            return  # layout 'name' is already the active layout

        blocks = self.doc.blocks
        new_active_paper_space_name = new_active_layout.block_record_name

        blocks.rename_block(PAPER_SPACE, TMP_PAPER_SPACE_NAME)
        blocks.rename_block(new_active_paper_space_name, PAPER_SPACE)
        blocks.rename_block(TMP_PAPER_SPACE_NAME, new_active_paper_space_name)

    def delete(self, name: str) -> None:
        """
        Delete layout `name` and all entities in it.

        Args:
            name (str): layout name as shown in tabs

        Raises:
            KeyError: if layout `name` do not exists
            ValueError: if `name` is ``Model`` (deleting model space)

        """
        if name == 'Model':
            raise DXFValueError("Can not delete model space layout.")

        layout = self._layouts[name]
        if layout.layout_key == self.doc.get_active_layout_key():  # name is the active layout
            for layout_name in self.names():
                if layout_name not in (name, 'Model'):  # set any other layout as active layout
                    self.set_active_layout(layout_name)
                    break
        self._dxf_layout_management_table.remove(layout.name)
        del self._layouts[layout.name]
        layout.destroy()

    def active_layout(self) -> 'Layout':
        """
        Returns active paper space layout.

        """
        for layout in self:
            if layout.block_record_name.upper() == '*PAPER_SPACE':
                return layout
        raise DXFInternalEzdxfError('No active paper space found.')

    def write_entities_section(self, tagwriter: 'TagWriter') -> None:
        """
        Write ``ENTITIES`` section to DXF file, the  ``ENTITIES`` section consist of all entities in model space and
        active paper space layout.

        All DXF entities of the remaining paper space layouts are stored in their associated ``BLOCK`` entity in the
        ``BLOCKS`` section.

        Args:
            tagwriter (TagWriter): tag writer object

        """
        self.modelspace().write(tagwriter)
        self.active_layout().write(tagwriter)


class BaseLayout(GraphicsFactory):
    """
    Base class for DXF12Layout() and DXF12BlockLayout()

    Entities are wrapped into class GraphicEntity() or inherited.

    """

    def __init__(self, dxffactory: 'EntityFactory', entity_space: 'EntitySpace'):
        super().__init__(dxffactory)
        self._entity_space = entity_space

    def __len__(self) -> int:
        """
        Entities count.

        """
        return len(self._entity_space)

    def __iter__(self) -> Iterable['DXFEntity']:
        """
        Iterate over all drawing entities in this layout.

        Returns: :class:`DXFEntity`

        """
        return iter(self._entity_space)

    @property
    def entitydb(self) -> 'EntityDB':
        return self._dxffactory.entitydb

    @property
    def drawing(self) -> 'Drawing':
        return self._dxffactory.doc

    @property
    def doc(self) -> 'Drawing':
        return self._dxffactory.doc

    def build_and_add_entity(self, type_: str, dxfattribs: dict) -> 'DXFEntity':
        """
        Create entity in drawing database and add entity to the entity space.

        Args:
            type_ (str): DXF type string, like 'LINE', 'CIRCLE' or 'LWPOLYLINE'
            dxfattribs (dict): DXF attributes for the new entity

        """
        entity = self.build_entity(type_, dxfattribs)
        self.add_entity(entity)
        return entity

    def build_entity(self, type_: str, dxfattribs: dict) -> 'DXFEntity':
        """
        Create entity in drawing database, returns a wrapper class inherited from GraphicEntity().

        Adds entity to the drawing database.

        Args:
            type_ (str): DXF type string, like 'LINE', 'CIRCLE' or 'LWPOLYLINE'
            dxfattribs(dict): DXF attributes for the new entity

        """
        entity = self._dxffactory.create_db_entry(type_, dxfattribs)
        self._set_paperspace(entity)
        return entity

    def add_entity(self, entity: 'DXFEntity') -> None:
        """
        Add an existing :class:`DXFEntity` to a layout, but be sure to unlink (:meth:`~Layout.unlink_entity()`) first the entity
        from the previous owner layout.

        """
        self._entity_space.add(entity)
        self._set_paperspace(entity)
        for linked_entity in entity.linked_entities():
            self._set_paperspace(linked_entity)

    def unlink_entity(self, entity: 'DXFEntity') -> None:
        """
        Unlink `entity` from layout but does not delete entity from the drawing database.

        Removes `entity` just from  entity space but not from the drawing database.

        Args:
            entity: :class:`DXFEntity`

        """
        self._entity_space.remove(entity)
        entity.dxf.paperspace = -1  # set invalid paper space
        entity.dxf.owner = '0'

    def delete_entity(self, entity: 'DXFEntity') -> None:
        """
        Delete `entity` from layout (entity space) and drawing database.

        Args:
            entity: :class:`DXFEntity`

        """
        self.entitydb.delete_entity(entity)  # 1. delete from drawing database
        self.unlink_entity(entity)  # 2. unlink from entity space

    def delete_all_entities(self) -> None:
        """
        Delete all entities from Layout (entity space) and from drawing database.

        """
        # noinspection PyTypeChecker
        for entity in list(self):  # temp list, because delete modifies the base data structure of the iterator
            self.delete_entity(entity)

    def _set_paperspace(self, entity: 'DXFEntity') -> None:
        pass  # only for DXF 2000 and later necessary

    def get_entity_by_handle(self, handle: str) -> 'DXFEntity':
        """
        Get entity by handle as GraphicEntity() or inherited.

        """
        return self.entitydb[handle]

    def query(self, query='*') -> EntityQuery:
        """
        Get all DXF entities matching the :ref:`entity query string`.

        Args:
            query: eintity query string

        Returns: :class:`EntityQuery`

        """
        return EntityQuery(iter(self), query)

    def groupby(self, dxfattrib: str = "", key: 'KeyFunc' = None) -> Dict[Hashable, List['DXFEntity']]:
        """
        Returns a dict of entity lists, where entities are grouped by a `dxfattrib` or a `key` function.

        Args:
            dxfattrib: grouping by DXF attribute like "layer"
            key: key function, which accepts a :class:`DXFEntity` as argument, returns grouping key of this entity or
                 None to ignore this object. Reason for ignoring: a queried DXF attribute is not supported by this
                 entity.

        """
        return groupby(iter(self), dxfattrib, key)

    def move_to_layout(self, entity: 'DXFEntity', layout: 'GenericLayoutType') -> None:
        """
        Move entity from block layout to another layout.

        Args:
            entity: DXF entity to move
            layout: any layout (model space, paper space, block)

        """
        if entity in self._entity_space:
            self.unlink_entity(entity)
            layout.add_entity(entity)
        else:
            raise DXFValueError('Layout does not contain entity.')


class Layout(BaseLayout):
    """
    Layout representation

    Every layout consist of a LAYOUT entity in the OBJECTS section, an associated BLOCK in the BLOCKS section and a
    BLOCK_RECORD_TABLE entry.

    layout_key: handle of the BLOCK_RECORD, every layout entity has this handle as owner attribute (entity.dxf.owner)

    There are 3 different layout types:

    1. Model Space - not deletable, all entities of this layout are stored in the DXF file in the ENTITIES section, the
       associated ``*Model_Space`` block is empty, block name ``*Model_Space`` is mandatory, the layout name is
       ``Model`` and it is mandatory.

    2. Active Layout - all entities of this layout are stored in the ENTITIES section, the associated ``*Paper_Space``
       block is empty, block name ``*Paper_Space`` is mandatory and also marks the active layout, the layout name can
       be an arbitrary string.

    3. Inactive Layout - all entities of this layouts are stored in the associated BLOCK called ``*Paper_SpaceN``, where
       ``N`` is an arbitrary number, I don't know if the block name schema '*Paper_SpaceN' is mandatory, the layout
       name can be an arbitrary string.

    There is no different handling for active layouts and inactive layouts in ezdxf, this differentiation is just
    for AutoCAD important and it is not documented in the DXF reference.

    Internal Structure

    For **every** layout exists a BlockLayout() object in the BLOCKS section and a Layout() object in Layouts().
    The entity space of the BlockLayout() object and the entity space of the Layout() object are the **same** object.

    """
    # plot_layout_flags of LAYOUT entity
    PLOT_VIEWPORT_BORDERS = 1
    SHOW_PLOT_STYLES = 2
    PLOT_CENTERED = 4
    PLOT_HIDDEN = 8
    USE_STANDARD_SCALE = 16
    PLOT_PLOTSTYLES = 32
    SCALE_LINEWEIGHTS = 64
    PRINT_LINEWEIGHTS = 128
    DRAW_VIEWPORTS_FIRST = 512
    MODEL_TYPE = 1024
    UPDATE_PAPER = 2048
    ZOOM_TO_PAPER_ON_UPDATE = 4096
    INITIALIZING = 8192
    PREV_PLOT_INIT = 16384

    def __init__(self, doc: 'Drawing', layout_handle: str):
        self.dxf_layout = doc.entitydb[layout_handle]
        self._block_record_handle = self.dxf_layout.dxf.block_record

        entity_space = self._get_layout_entity_space(doc, self.dxf_layout)
        super().__init__(doc.dxffactory, entity_space)
        self._layout_handle = layout_handle
        self._paperspace = 0 if self.name == 'Model' else 1
        self._repair_owner_tags()

    @property
    def name(self) -> str:
        """
        Returns layout name (as shown in tabs).

        """
        return self.dxf_layout.dxf.name

    @property
    def dxf(self) -> Any:  # dynamic DXF attribute dispatching, e.g. DXFLayout.dxf.layout_flags
        """
        Returns the DXF name space attribute of the associated DXF ``LAYOUT`` entity.

        This enables direct access to the ``LAYOUT`` entity, e.g. Layout.dxf.layout_flags

        """
        return self.dxf_layout.dxf

    @property
    def layout_key(self) -> str:
        """
        Returns the layout key as string.

        The layout key is the handle of the associated ``BLOCK_RECORD`` entry in the ``BLOCK_RECORDS`` table.

        """
        return self._block_record_handle

    @property
    def block_record(self) -> 'BlockRecord':
        """
        Returns the associated ``BLOCK_RECORD``.

        """
        return self.drawing.dxffactory.wrap_handle(self._block_record_handle)

    @property
    def block_record_name(self) -> str:
        """
        Returns the name of the associated ``BLOCK_RECORD`` as string.

        """
        return self.block_record.dxf.name

    @property
    def block(self) -> 'BlockLayout':
        """
        Returns the associated `BlockLayout` object.

        """
        return self.drawing.blocks.get(self.block_record_name)

    def _set_paperspace(self, entity: 'DXFEntity') -> None:
        """
        Set correct `owner` and `paperspace` attribute, to be a valid member of this layout.

        Args:
            entity (DXFEntiy): generic DXF entity

        """
        entity.dxf.paperspace = self._paperspace
        entity.dxf.owner = self.layout_key

    @staticmethod
    def _get_layout_entity_space(doc: 'Drawing', layout: 'Layout') -> 'EntitySpace':
        block_record = doc.entitydb[layout.dxf.block_record]
        block = doc.blocks.get(block_record.dxf.name)
        return block.get_entity_space()

    def _repair_owner_tags(self) -> None:
        """
        Set `owner` and `paperspace` attributes of entities hosted by this layout to correct values.

        """
        layout_key = self.layout_key
        paper_space = self._paperspace
        for entity in self:
            if entity.get_dxf_attrib('owner', default=None) != layout_key:
                entity.set_dxf_attrib('owner', layout_key)
            if entity.get_dxf_attrib('paperspace', default=0) != paper_space:
                entity.set_dxf_attrib('paperspace', paper_space)

    def __contains__(self, entity: Union['DXFEntity', str]) -> bool:
        if isinstance(entity, str):  # entity is a handle string
            entity = self.entitydb[entity]
        return entity.dxf.owner == self.layout_key

    def destroy(self) -> None:
        """
        Delete all member entities and the layout itself from entity database and all other structures.

        """
        self.delete_all_entities()
        self.drawing.blocks.delete_block(self.block.name)
        self.drawing.objects.remove_handle(self._layout_handle)
        self.drawing.entitydb.delete_handle(self._layout_handle)

    def viewports(self) -> List['DXFEntity']:
        """
        Get all VIEWPORT entities defined in the layout. Returns a list of Viewport() objects, sorted by id, the first
        entity is always the paper space view with the id=1.

        """
        vports = [entity for entity in self if entity.dxftype() == 'VIEWPORT']
        vports.sort(key=lambda e: e.dxf.id)
        return vports

    def renumber_viewports(self) -> None:
        for num, viewport in enumerate(self.viewports(), start=1):
            viewport.dxf.id = num

    def write(self, tagwriter: 'TagWriter') -> None:
        self._entity_space.write(tagwriter)

    def add_viewport_r12(self,
                         center: Tuple[float, float],
                         size: Tuple[float, float],
                         view_center_point: Tuple[float, float],
                         view_height: float,
                         dxfattribs: dict = None) -> 'DXFEntity':
        if dxfattribs is None:
            dxfattribs = {}
        else:
            dxfattribs = dict(dxfattribs)
        width, height = size
        attribs = {
            'center': center,
            'width': width,
            'height': height,
            'status': 1,  # by default highest priority (stack order)
            'layer': 'VIEWPORTS',  # use separated layer to turn off for plotting
        }
        attribs.update(dxfattribs)
        # DXF R12 (AC1009): view_center_point and view_height (as many other viewport attributes) are not usual
        # DXF attributes, they are stored as extended DXF tags.
        viewport = self.build_and_add_entity('VIEWPORT', attribs)
        viewport.dxf.id = viewport.get_next_viewport_id()
        with viewport.edit_data() as vp_data:
            vp_data.view_center_point = view_center_point
            vp_data.view_height = view_height
        return viewport

    def add_viewport(self, center: 'Vertex',
                     size: Tuple[float, float],
                     view_center_point: 'Vertex',
                     view_height: float,
                     dxfattribs: dict = None) -> 'Viewport':
        dxfattribs = dxfattribs or {}
        width, height = size
        attribs = {
            'center': center,
            'width': width,
            'height': height,
            'status': 1,  # by default highest priority (stack order)
            'layer': 'VIEWPORTS',  # use separated layer to turn off for plotting
            'view_center_point': view_center_point,
            'view_height': view_height,
        }
        attribs.update(dxfattribs)
        viewport = cast('Viewport', self.build_and_add_entity('VIEWPORT', attribs))
        viewport.dxf.id = viewport.get_next_viewport_id()
        return viewport

    def get_extension_dict(self, create: bool = True) -> 'DXFDictionary':
        """
        Returns the associated extension dictionary.

        Args:
            create (bool): create extension dictionary if not exists

        Raises:
            DXFValueError: if extension dictionary do not exists and `create` is False

        """
        block_record = self.block_record
        try:
            xdict = block_record.get_extension_dict()
        except (DXFValueError, DXFKeyError):
            # DXFValueError: block_record has no extension dict
            # DXFKeyError: block_record has an extension dict handle, but extension dict does not exist
            if create:
                xdict = block_record.new_extension_dict()
            else:
                raise DXFValueError('Extension dictionary do not exist.')
        return xdict

    def new_geodata(self, dxfattribs: dict = None) -> 'GeoData':
        """
        Creates a new :class:`GeoData` entity and replaces existing ones. The GEODATA entity resides in the OBJECTS section
        and NOT in the layout entity space and it is linked to the layout by an extension dictionary located in BLOCK_RECORD
        of the layout.

        The GEODATA entity requires DXF version R2010+. The DXF Reference does not document if other layouts than model
        space supports geo referencing, so getting/setting geo data may only make sense for the model space layout, but
        it is also available in paper space layouts.

        Args:
            dxfattribs (dict): DXF attributes for the :class:`GeoData` entity

        """
        if dxfattribs is None:
            dxfattribs = {}
        dwg = self.drawing
        if dwg.dxfversion < 'AC1024':
            raise DXFValueError('GEODATA entity requires DXF version R2010 (AC1024) or later.')
        xdict = self.get_extension_dict(create=True)
        geodata = dwg.objects.add_geodata(
            owner=xdict.dxf.handle,
            dxfattribs=dxfattribs,
        )
        xdict['ACAD_GEOGRAPHICDATA'] = geodata.dxf.handle
        return geodata

    def get_geodata(self) -> Optional['GeoData']:
        """
        Returns the :class:`GeoData` entity associated to this layout or None.

        """
        try:
            xdict = self.block_record.get_extension_dict()
        except DXFValueError:
            return None
        try:
            return xdict.get_entity('ACAD_GEOGRAPHICDATA')
        except DXFKeyError:
            return None

    def get_sortents_table(self, create: bool = True) -> 'SortEntitiesTable':
        """
        Get/Create to layout associated ``SORTENTSTABLE`` object.

        Args:
            create (bool): new table if table do not exists and create is True

        Raises:
            DXFValueError: if table not exists and `create` is False

        """
        xdict = self.get_extension_dict(create=True)
        try:
            sortents_table = xdict.get_entity('ACAD_SORTENTS')
        except DXFKeyError:
            if create:
                sortents_table = self.drawing.objects.create_new_dxf_entity(
                    'SORTENTSTABLE',
                    dxfattribs={
                        'owner': xdict.dxf.handle,
                        'block_record': self.layout_key
                    },
                )
                xdict['ACAD_SORTENTS'] = sortents_table.dxf.handle
            else:
                raise DXFValueError('Extension dictionary entry ACAD_SORTENTS do not exist.')
        return sortents_table

    def set_redraw_order(self, handles: Union[Dict, Iterable[Tuple[str, str]]]) -> None:
        """
        If the header variable $SORTENTS `Regen` flag (bit-code value 16) is set, AutoCAD regenerates entities in
        ascending handles order.

        To change redraw order associate a different sort handle to entities, this redefines the order in which the
        entities are regenerated. `handles` can be a dict of object_handle and sort_handle as (key, value) pairs, or an
        iterable of (object_handle,  sort_handle) tuples.

        The sort_handle doesn't have to be unique, same or all handles can share the same sort_handle and sort_handles
        can use existing handles too.

        The '0' handle can be used, but this sort_handle will be drawn as latest (on top of all other entities) and not
        as first as expected.

        Args:
            handles: iterable or dict of handle associations; for iterable an association
                     is a tuple (object_handle, sort_handle); for dict the association is
                     key: object_handle, value: sort_handle

        """
        sortents = self.get_sortents_table()
        if isinstance(handles, dict):
            handles = handles.items()
        sortents.set_handles(handles)

    def get_redraw_order(self) -> Iterable[Tuple[str, str]]:
        """
        Returns iterable for all existing table entries as (object_handle, sort_handle) pairs.
        (see also :meth:`~Layout.set_redraw_order`)

        """
        empty = []
        try:
            xdict = self.get_extension_dict(create=False)
        except DXFValueError:
            return empty
        try:
            sortents_table = xdict.get_entity('ACAD_SORTENTS')
        except DXFKeyError:
            return empty
        return iter(sortents_table)

    def page_setup_r12(self, size: Tuple[int, int] = (297, 210),
                       margins: Tuple[int, int, int, int] = (0, 0, 0, 0),
                       units: str = 'mm',
                       offset: Tuple[int, int] = (0, 0),
                       rotation: float = 0,
                       scale: int = 16) -> None:
        if self._paperspace == 0:
            raise DXFTypeError("No paper setup for model space.")

        # remove existing viewports
        for viewport in self.viewports():
            self.delete_entity(viewport)

        if int(rotation) not in (0, 1, 2, 3):
            raise DXFValueError("valid rotation values: 0-3")

        if isinstance(scale, int):
            scale = STD_SCALES.get(scale, (1, 1))

        if scale[0] == 0:
            raise DXFValueError("scale numerator can't be 0.")
        if scale[1] == 0:
            raise DXFValueError("scale denominator can't be 0.")

        scale_factor = scale[1] / scale[0]

        # TODO: don't know how to set inch or mm mode in R12
        units = units.lower()
        if units.startswith('inch'):
            units = 'Inches'
            plot_paper_units = 0
            unit_factor = 25.4  # inch to mm
        elif units == 'mm':
            units = 'MM'
            plot_paper_units = 1
            unit_factor = 1.0
        else:
            raise DXFValueError('Supported units: "mm" and "inch"')

        # all viewport parameters are scaled paper space units
        def paper_units(value):
            return value * scale_factor

        # TODO: don't know how paper setup in DXF R12 works
        paper_width, paper_height = size

        # TODO: don't know how margins setup in DXF R12 works
        margin_top, margin_right, margin_bottom, margin_left = margins

        paper_width = paper_units(size[0])
        paper_height = paper_units(size[1])

        plimmin = self.drawing.header['$PLIMMIN'] = (0, 0)
        plimmax = self.drawing.header['$PLIMMAX'] = (paper_width, paper_height)

        # TODO: don't know how paper setup in DXF R12 works

        pextmin = self.drawing.header['$PEXTMIN'] = (0, 0, 0)
        pextmax = self.drawing.header['$PEXTMAX'] = (paper_width, paper_height, 0)

        # printing area
        printable_width = paper_width - paper_units(margin_left) - paper_units(margin_right)
        printable_height = paper_height - paper_units(margin_bottom) - paper_units(margin_top)

        # AutoCAD viewport (window) size
        vp_width = paper_width * 1.1
        vp_height = paper_height * 1.1

        # center of printing area
        center = (printable_width / 2, printable_height / 2)

        # create 'main' viewport
        main_viewport = self.add_viewport(
            center=center,  # no influence to 'main' viewport?
            size=(vp_width, vp_height),  # I don't get it, just use paper size!
            view_center_point=center,  # same as center
            view_height=vp_height,  # view height in paper space units
        )
        main_viewport.dxf.id = 1  # set as main viewport
        main_viewport.dxf.status = 2  # AutoCAD default value
        with main_viewport.edit_data() as vpdata:
            vpdata.view_mode = 1000  # AutoDesk default

    def get_paper_limits_r12(self) -> Tuple[float, float]:
        """
        Returns paper limits in plot paper units

        """
        limmin = self.drawing.header.get('$PLIMMIN', (0, 0))
        limmax = self.drawing.header.get('$PLIMMAX', (0, 0))
        return limmin, limmax

    def page_setup(self, size: Tuple[int, int] = (297, 210),
                   margins: Tuple[float, float, float, float] = (10, 15, 10, 15),
                   units: str = 'mm',
                   offset: Tuple[float, float] = (0, 0),
                   rotation: int = 0,
                   scale: int = 16,
                   name: str = 'ezdxf',
                   device: str = 'DWG to PDF.pc3') -> None:
        """
        Setup plot settings and paper size and reset viewports. All parameters in given `units` (mm or inch).

        Args:
            size: paper size as (width, height) tuple
            margins: (top, right, bottom, left) hint: clockwise
            units: "mm" or "inch"
            offset: plot origin offset is 2D point
            rotation: see table `Rotation`
            scale: int 0-32 = standard scale type or tuple(numerator, denominator) e.g. (1, 50) for 1:50
            name: paper name prefix '{name}_({width}_x_{height}_{unit})'
            device: device .pc3 configuration file or system printer name

        === ============
        int Rotation
        === ============
        0   no rotation
        1   90 degrees counter-clockwise
        2   upside-down
        3   90 degrees clockwise
        === ============

        """
        if self.name == 'Model':
            raise DXFTypeError("No paper setup for model space.")
        if int(rotation) not in (0, 1, 2, 3):
            raise DXFValueError("valid rotation values: 0-3")

        if isinstance(scale, tuple):
            standard_scale = 16
        elif isinstance(scale, int):
            standard_scale = scale
            scale = STD_SCALES.get(standard_scale, (1, 1))
        else:
            raise DXFTypeError("scale has to be an int or a tuple(numerator, denominator)")
        if scale[0] == 0:
            raise DXFValueError("scale numerator can't be 0.")
        if scale[1] == 0:
            raise DXFValueError("scale denominator can't be 0.")

        self.use_standard_scale(False)  # works best, don't know why
        paper_width, paper_height = size
        margin_top, margin_right, margin_bottom, margin_left = margins
        units = units.lower()
        if units.startswith('inch'):
            units = 'Inches'
            plot_paper_units = 0
            unit_factor = 25.4  # inch to mm
        elif units == 'mm':
            units = 'MM'
            plot_paper_units = 1
            unit_factor = 1.0
        else:
            raise DXFValueError('Supported units: "mm" and "inch"')

        # Setup PLOTSETTINGS
        # all paper sizes in mm
        dxf = self.dxf_layout.dxf
        dxf.page_setup_name = ''
        dxf.plot_configuration_file = device
        dxf.paper_size = '{0}_({1:.2f}_x_{2:.2f}_{3})'.format(name, paper_width, paper_height, units)
        dxf.left_margin = margin_left * unit_factor
        dxf.bottom_margin = margin_bottom * unit_factor
        dxf.right_margin = margin_right * unit_factor
        dxf.top_margin = margin_top * unit_factor
        dxf.paper_width = paper_width * unit_factor
        dxf.paper_height = paper_height * unit_factor
        dxf.scale_numerator = scale[0]
        dxf.scale_denominator = scale[1]
        dxf.plot_paper_units = plot_paper_units
        dxf.plot_rotation = rotation

        x_offset, y_offset = offset
        dxf.plot_origin_x_offset = x_offset * unit_factor  # conversion to mm
        dxf.plot_origin_y_offset = y_offset * unit_factor  # conversion to mm
        dxf.standard_scale_type = standard_scale
        dxf.unit_factor = 1. / unit_factor  # 1/1 for mm; 1/25.4 ... for inch

        # Setup Layout
        self.reset_paper_limits()
        self.reset_extends()
        self.reset_viewports()

    def reset_extends(self) -> None:
        """
        Reset paper space extends. (in :meth:`~Layout.page_setup` included)

        """
        dxf = self.dxf_layout.dxf
        dxf.extmin = (+1e20, +1e20, +1e20)  # AutoCAD default
        dxf.extmax = (-1e20, -1e20, -1e20)  # AutoCAD default

    def reset_paper_limits(self) -> None:
        """
        Set paper limits to default values, all values in paper space units but without plot scale (?).
        (in :meth:`~Layout.page_setup` included)

        """
        dxf = self.dxf_layout.dxf
        if dxf.plot_paper_units == 0:  # inch
            unit_factor = 25.4
        else:  # mm
            unit_factor = 1.0

        # all paper sizes are stored in mm
        paper_width = dxf.paper_width / unit_factor  # in plot paper units
        paper_height = dxf.paper_height / unit_factor  # in plot paper units
        left_margin = dxf.left_margin / unit_factor
        bottom_margin = dxf.bottom_margin / unit_factor
        x_offset = dxf.plot_origin_x_offset / unit_factor
        y_offset = dxf.plot_origin_y_offset / unit_factor
        # plot origin is the lower left corner of the printable paper area
        # limits are the paper borders relative to the plot origin
        shift_x = left_margin + x_offset
        shift_y = bottom_margin + y_offset
        dxf.limmin = (-shift_x, -shift_y)  # paper space units
        dxf.limmax = (paper_width - shift_x, paper_height - shift_y)

    def get_paper_limits(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """
        Returns paper limits in plot paper units, relative to the plot origin, as tuple ((x1, y1), (x2, y2)).
        Lower left corner is (x1, y1), upper right corner is (x2, y2).

        plot origin = lower left corner of printable area + plot origin offset

        """
        return self.dxf.limmin, self.dxf.limmax

    def reset_viewports(self) -> None:
        """
        Delete all existing viewports, and add a new main viewport. (in :meth:`~Layout.page_setup` included)

        """
        # remove existing viewports
        for viewport in self.viewports():
            self.delete_entity(viewport)
        self.add_new_main_viewport()

    def add_new_main_viewport(self) -> None:
        """
        Add a new main viewport.

        """
        dxf = self.dxf_layout.dxf
        if dxf.plot_paper_units == 0:  # inches
            unit_factor = 25.4
        else:  # mm
            unit_factor = 1.0

        # all paper parameters in mm!
        # all viewport parameters in paper space units inch/mm + scale factor!
        scale_factor = dxf.scale_denominator / dxf.scale_numerator

        def paper_units(value):
            return value / unit_factor * scale_factor

        paper_width = paper_units(dxf.paper_width)
        paper_height = paper_units(dxf.paper_height)
        # plot origin offset
        x_offset = paper_units(dxf.plot_origin_x_offset)
        y_offset = paper_units(dxf.plot_origin_y_offset)

        # printing area
        printable_width = paper_width - paper_units(dxf.left_margin) - paper_units(dxf.right_margin)
        printable_height = paper_height - paper_units(dxf.bottom_margin) - paper_units(dxf.top_margin)

        # AutoCAD viewport (window) size
        vp_width = paper_width * 1.1
        vp_height = paper_height * 1.1

        # center of printing area
        center = (printable_width / 2 - x_offset, printable_height / 2 - y_offset)

        # create 'main' viewport
        main_viewport = self.add_viewport(
            center=center,  # no influence to 'main' viewport?
            size=(vp_width, vp_height),  # I don't get it, just use paper size!
            view_center_point=center,  # same as center
            view_height=vp_height,  # view height in paper space units
        )
        main_viewport.dxf.id = 1  # set as main viewport
        main_viewport.dxf.flags = 557088  # AutoCAD default value
        dxf.viewport = main_viewport.dxf.handle

    def set_plot_type(self, value: int = 5) -> None:
        """
        === ============================================================
        0   last screen display
        1   drawing extents
        2   drawing limits
        3   view specific (defined by Layout.dxf.plot_view_name)
        4   window specific (defined by Layout.set_plot_window_limits())
        5   layout information (default)
        === ============================================================

        Args:
            value:  plot type

        Raises:
            DXFValueError: for `value` out of range

        """
        if 0 <= int(value) <= 5:
            self.dxf.plot_type = value  # type: ignore
        else:
            raise DXFValueError('Plot type value out of range (0-5).')

    def set_plot_style(self, name: str = 'ezdxf.ctb', show: bool = False) -> None:
        """
        Set plot style file of type `ctb`.

        Args:
            name: plot style filename
            show: show plot style effect in preview? (AutoCAD specific attribute)

        """
        self.dxf_layout.dxf.current_style_sheet = name
        self.use_plot_styles(True)
        self.show_plot_styles(show)

    def set_plot_window(self,
                        lower_left: Tuple[float, float] = (0, 0),
                        upper_right: Tuple[float, float] = (0, 0)) -> None:
        """
        Set plot window size in (scaled) paper space units.

        Args:
            lower_left: lower left corner as 2D point
            upper_right: upper right corner as 2D point

        """
        x1, y1 = lower_left
        x2, y2 = upper_right
        dxf = self.dxf_layout.dxf
        dxf.plot_window_x1 = x1
        dxf.plot_window_y1 = y1
        dxf.plot_window_x2 = x2
        dxf.plot_window_y2 = y2
        self.set_plot_type(4)

    # plot layout flags setter
    def plot_viewport_borders(self, state: bool = True) -> None:
        self.set_plot_flags(self.PLOT_VIEWPORT_BORDERS, state)

    def show_plot_styles(self, state: bool = True) -> None:
        self.set_plot_flags(self.SHOW_PLOT_STYLES, state)

    def plot_centered(self, state: bool = True) -> None:
        self.set_plot_flags(self.PLOT_CENTERED, state)

    def plot_hidden(self, state: bool = True) -> None:
        self.set_plot_flags(self.PLOT_HIDDEN, state)

    def use_standard_scale(self, state: bool = True) -> None:
        self.set_plot_flags(self.USE_STANDARD_SCALE, state)

    def use_plot_styles(self, state: bool = True) -> None:
        self.set_plot_flags(self.PLOT_PLOTSTYLES, state)

    def scale_lineweights(self, state: bool = True) -> None:
        self.set_plot_flags(self.SCALE_LINEWEIGHTS, state)

    def print_lineweights(self, state: bool = True) -> None:
        self.set_plot_flags(self.PRINT_LINEWEIGHTS, state)

    def draw_viewports_first(self, state: bool = True) -> None:
        self.set_plot_flags(self.PRINT_LINEWEIGHTS, state)

    def model_type(self, state: bool = True) -> None:
        self.set_plot_flags(self.MODEL_TYPE, state)

    def update_paper(self, state: bool = True) -> None:
        self.set_plot_flags(self.UPDATE_PAPER, state)

    def zoom_to_paper_on_update(self, state: bool = True) -> None:
        self.set_plot_flags(self.ZOOM_TO_PAPER_ON_UPDATE, state)

    def plot_flags_initializing(self, state: bool = True) -> None:
        self.set_plot_flags(self.INITIALIZING, state)

    def prev_plot_init(self, state: bool = True) -> None:
        self.set_plot_flags(self.PREV_PLOT_INIT, state)

    def set_plot_flags(self, flag, state: bool = True) -> None:
        self.dxf_layout.set_flag_state(flag, state=state, name='plot_layout_flags')


class BlockLayout(BaseLayout):
    """
    BlockLayout has the same factory-function as Layout, but is managed
    in the BlocksSection() class. It represents a DXF Block definition.

    Attributes:
        block:  BLOCK entity
        endblk: ENDBLK entity
        _entityspace: is the block content

    """

    def __init__(self, entitydb: 'EntityDB', dxffactory: 'EntityFactory', block_handle: str, endblk_handle: str):
        super().__init__(dxffactory, EntitySpace())
        self.block = self.entitydb[block_handle]
        self.endblk = self.entitydb[endblk_handle]

    def __contains__(self, entity: 'DXFEntity') -> bool:
        """
        Returns True if block contains entity else False. *entity* can be a handle-string, Tags(),
        ExtendedTags() or a wrapped entity.

        """
        if isinstance(entity, str):
            entity = self.entitydb[entity]
        return entity in self._entity_space

    @property
    def name(self) -> str:
        """ Get block name """
        return self.block.dxf.name

    @name.setter
    def name(self, new_name) -> None:
        """ Set block name """
        block = self.block
        block.dxf.name = new_name
        block.dxf.name2 = new_name

    @property
    def block_record_handle(self) -> str:
        return self.block.dxf.owner

    @property
    def block_record(self) -> 'BlockRecord':
        return self.entitydb[self.block_record_handle]

    def set_block_record_handle(self, block_record_handle: str) -> None:
        self.block.dxf.owner = block_record_handle
        self.endblk.dxf.owner = block_record_handle

    @property
    def is_layout_block(self) -> bool:
        """
        True if block is a model space or paper space block definition.

        """
        return self.block.is_layout_block

    def get_entity_space(self) -> EntitySpace:
        return self._entity_space

    def set_entity_space(self, entity_space: EntitySpace) -> None:
        self._entity_space = entity_space

    def add_attdef(self, tag: str, insert: Sequence[float] = (0, 0), text: str = '',
                   dxfattribs: dict = None) -> 'DXFEntity':
        """
        Add an :class:`Attdef` entity.

        Set position and alignment by the idiom::

            myblock.add_attdef('NAME').set_pos((2, 3), align='MIDDLE_CENTER')

        Args:
            tag: attribute name (tag) as string without spaces
            insert: attribute insert point relative to block origin (0, 0, 0)
            text: preset text for attribute

        """
        if dxfattribs is None:
            dxfattribs = {}
        dxfattribs['tag'] = tag
        dxfattribs['insert'] = insert
        dxfattribs['text'] = text
        return self.build_and_add_entity('ATTDEF', dxfattribs)

    def attdefs(self) -> Iterable['DXFEntity']:
        """
        Iterate for all :class:`Attdef` entities.

        """
        return (entity for entity in self if entity.dxftype() == 'ATTDEF')

    def has_attdef(self, tag: str) -> bool:
        """
        Returns `True` if an :class:`Attdef` for `tag` exists else `False`.

        Args:
            tag: tag name

        """
        return self.get_attdef(tag) is not None

    def get_attdef(self, tag: str) -> Optional['DXFEntity']:
        """
        Get attached :class:`Attdef` entity by `tag`.

        Args:
            tag: tag name

        Returns: :class:`Attdef`

        """
        for attdef in self.attdefs():
            if tag == attdef.dxf.tag:
                return attdef

    def get_attdef_text(self, tag: str, default: str = None) -> str:
        """
        Get content text for :class:`Attdef` `tag` as string or returns `default` if no :class:`Attdef` for `tag` exists.

        Args:
            tag: tag name
            default: default value if tag is absent

        """
        attdef = self.get_attdef(tag)
        if attdef is None:
            return default
        return attdef.dxf.text

    # end of public interface

    def add_entity(self, entity: 'DXFEntity') -> None:
        """
        Add an existing DXF entity to a layout, but be sure to unlink (:meth:`~Layout.unlink_entity()`) first the entity
        from the previous owner layout.

        Args:
            entity: :class:`DXFEntity`

        """
        # set a model space, because paper space layout is a different class
        entity.set_owner(self.block_record_handle, paperspace=0)
        self._entity_space.add(entity)

    def add_handle(self, handle: str) -> None:
        """
        Add entity by handle to the block entity space.

        """
        self.add_entity(self.entitydb[handle])

    def export_dxf_block(self, tagwriter: 'TagWriter') -> None:
        self.block.export_dxf(tagwriter)
        self._entity_space.export_dxf(tagwriter)
        self.endblk.export_dxf(tagwriter)

    def export_dxf(self, tagwriter: 'TagWriter'):
        # BLOCK section: do not write content of model space and active layout
        if self.name.upper() in {'*MODEL_SPACE', '*PAPER_SPACE', '$MODEL_SPACE', '$PAPER_SPACE'}:
            save = self._entity_space
            self._entity_space = EntitySpace()
            self.export_dxf_block(tagwriter)
            self._entity_space = save
        else:
            self.export_dxf_block(tagwriter)

    def delete_all_entities(self) -> None:
        # 1. delete from database
        for entity in self._entity_space:
            self.entitydb.delete_entity(entity)
        # 2. delete from entity space
        self._entity_space.clear()

    def destroy(self) -> None:
        self.doc.sections.tables.block_records.remove_handle(self.block_record_handle)
        self.delete_all_entities()
        self.entitydb.delete_entity(self.block)
        self.entitydb.delete_entity(self.endblk)

    def get_const_attdefs(self) -> Iterable['DXFEntity']:
        """
        Returns a generator for constant ATTDEF entities.

        """
        return (attdef for attdef in self.attdefs() if attdef.is_const)

