import hashlib
import typing
import json

import legion.k8s.crd
import legion.k8s.definitions as defs
from .definitions import *

MergeResult = typing.NamedTuple('MergeResult', (
    ('state_update', typing.Optional[dict]),
    ('create_child', ChildInstanceCollection),
    ('remove_child', ChildInstanceCollection),
    ('inplace_update_child', ChildInstanceCollection)
))

DiffInfo = typing.NamedTuple('DiffInfo', (
    ('message', str),
    ('old', object),
    ('new', object),
))


def _build_hashtable(instances: ChildInstanceCollection) -> typing.Dict[typing.Tuple[type, str], object]:
    if instances is None:
        return {}

    return {
        (instance.type, instance.name): instance.instance
        for instance
        in instances
    }
#
#
# def _get_obj_field(obj: object, field: str) -> typing.Optional[object]:
#     field_parts = field.split('.')
#
#     current_object = obj
#     for subfield_name in field_parts:
#         if current_object is None:
#             raise Exception('Sub field value is None')
#         if hasattr(current_object, subfield_name):
#             current_object = getattr(current_object, subfield_name)
#         elif isinstance(current_object, dict):
#             if subfield_name not in current_object:
#                 raise Exception('Cannot find sub field in dict')
#             current_object = current_object[subfield_name]
#         else:
#             raise Exception('Cannot find sub field')
#     return current_object
#
#
# def find_object_diffs(old: object, new: object) -> typing.Tuple[DiffInfo, ...]:
#     if type(old) != type(new):
#         return DiffInfo('Different types', type(old), type(new)),
#
#     if hasattr(old, 'to_dict'):
#         old = old.to_dict()
#         new = new.to_dict()
#
#     if isinstance(old, dict):
#         old_keys, new_keys = old.keys(), new.keys()
#         if old_keys != new_keys:
#             return DiffInfo('Different dict keys', old_keys, new_keys),
#
#         diffs = []
#         for key in old_keys:
#             a_value = old.get(key)
#             b_value = new.get(key)
#
#             sub_diffs = find_object_diffs(a_value, b_value)
#             for diff in sub_diffs:
#                 diffs.append(DiffInfo('Key {}: {}'.format(key, diff.message), diff.old, diff.new))
#
#         return tuple(diffs)
#     else:
#         if old != new:
#             return DiffInfo('Different objects', old, new),
#         else:
#             return tuple()


def force_k8s_instance_to_dict(obj: object) -> dict:
    if hasattr(obj, 'to_dict') and callable(obj.to_dict):
        obj = obj.to_dict()
    if not isinstance(obj, dict):
        raise Exception('Cannot interpret item as object')
    return obj


def compute_k8s_object_hash(obj: object) -> str:
    val_to_hash = json.dumps(force_k8s_instance_to_dict(obj))
    hashed_value = hashlib.sha1(val_to_hash.encode('utf-8')).hexdigest()
    return hashed_value


def get_k8s_object_hash_record(obj: object) -> str:
    obj_as_dict = force_k8s_instance_to_dict(obj)
    metadata = obj_as_dict.get('metadata', {})
    labels = metadata.get('labels', {})
    return labels.get(defs.LEGION_CRD_CHILD_REVISION)


def _is_object_updated(a: object, b: object) -> bool:
    old_hash = get_k8s_object_hash_record(a)
    new_hash = compute_k8s_object_hash(b)
    return old_hash != new_hash


def merge(event_object: legion.k8s.crd.BaseCRD,
          actual_child: ChildInstanceCollection,
          desired_state: DesiredState,
          child_types: typing.Tuple[ChildReferenceDeclaration, ...]) -> MergeResult:
    state_update = None
    create_child: typing.List[ChildInstancePair] = []
    remove_child: typing.List[ChildInstancePair] = []
    inplace_update_child: typing.List[ChildInstancePair] = []

    # 1s - merge state update
    if desired_state.status:
        has_diffs = False
        for field, value in desired_state.status.items():
            if event_object.status.get(field) != value:
                has_diffs = True
                break
        if has_diffs:
            state_update = desired_state.status

    actual_hashmap = _build_hashtable(actual_child)
    desired_hashmap = _build_hashtable(desired_state.child)

    # 2nd - create missed and update existed
    for (instance_type, name), instance in desired_hashmap.items():
        key = (instance_type, name)
        is_update = key in actual_hashmap
        if is_update:
            if _is_object_updated(actual_hashmap[key], instance):
                inplace_update_child.append(ChildInstancePair(instance_type, name, instance))
        else:
            create_child.append(ChildInstancePair(instance_type, name, instance))

    for (instance_type, name), instance in actual_hashmap.items():
        is_remove = (instance_type, name) not in desired_hashmap
        if is_remove:
            remove_child.append(ChildInstancePair(instance_type, name, instance))

    return MergeResult(
        state_update=state_update,
        create_child=tuple(create_child),
        remove_child=tuple(remove_child),
        inplace_update_child=tuple(inplace_update_child)
    )
