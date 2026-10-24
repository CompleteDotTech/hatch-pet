"""Reference camera math using authoritative rig quaternion and basis utilities.

Column vectors; parent@local; right-handed Y-up world; local -Z view, +Y up.
NDC depth is OpenGL/glTF [-1,+1]; raster coordinates use top-left pixel edges.
These functions do not perform rendering or claim browser/Blender parity.
"""
from __future__ import annotations

import math


def _numeric():
    import numpy as np
    import rig_math
    return np, rig_math


def _matrix(value, *, rigid=False):
    np, _ = _numeric()
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != (4,4) or not np.isfinite(matrix).all():
        raise ValueError('camera3d requires finite 4x4 matrix')
    if rigid and (not np.allclose(matrix[3],[0,0,0,1],atol=1e-9)
            or not np.allclose(matrix[:3,:3].T@matrix[:3,:3],np.eye(3),atol=1e-8)
            or not math.isclose(float(np.linalg.det(matrix[:3,:3])),1,abs_tol=1e-8)):
        raise ValueError('camera3d world matrix must be a rigid proper affine transform')
    sign, logdet = np.linalg.slogdet(matrix)
    if sign == 0 or not math.isfinite(float(logdet)):
        raise ValueError('camera3d matrix is singular')
    return matrix


def world_transform(transform, parent=None):
    np, rig = _numeric()
    if set(transform) != {'translation','rotation','scale'} or list(transform['scale']) != [1,1,1]:
        raise ValueError('camera3d camera transforms require unit scale')
    rig.quaternion(transform['rotation'],strict=True)
    local = rig.transform_matrix(transform)
    return _matrix((np.eye(4) if parent is None else _matrix(parent,rigid=True))@local,rigid=True)


def basis_transform(matrix, destination='blender'):
    """Convert world and camera-local bases by conjugation; glTF is identity."""
    np, rig = _numeric()
    matrix = _matrix(matrix,rigid=True)
    if destination == 'gltf':
        return matrix.copy()
    if destination not in ('blender','canonical-from-blender'):
        raise ValueError('camera3d unsupported basis')
    basis = rig.BLENDER_FROM_CANONICAL
    if destination == 'canonical-from-blender':
        basis = basis.T
    return basis@matrix@basis.T


def blender_camera_transform(matrix):
    """Convert world basis only: Blender camera-local -Z/+Y already matches ours."""
    _, rig = _numeric()
    return rig.BLENDER_FROM_CANONICAL@_matrix(matrix,rigid=True)


def canonical_camera_transform(matrix):
    _, rig = _numeric()
    return rig.BLENDER_FROM_CANONICAL.T@_matrix(matrix,rigid=True)


def look_at(position, target, up=(0,1,0)):
    np, rig = _numeric()
    position, target, up = rig.vector(position),rig.vector(target),rig.unit(up)
    backward = rig.unit(position-target)
    right = np.cross(up,backward)
    if np.linalg.norm(right) < 1e-8:
        raise ValueError('camera3d target direction is parallel to up')
    right = rig.unit(right)
    rotation = np.column_stack((right,np.cross(backward,right),backward))
    return rig.matrix_quaternion(rotation)


def projection_matrix(optics, render):
    """Pure pinhole/orthographic reference, excluding lens distortion and DOF.

    shift_x/y locate the principal point relative to image center, in fractions
    of full width/height (+X right,+Y up). Adapter optical sign conversion must
    be explicit. Overscan expands the frustum; nominal width/height stay fixed.
    """
    np, _ = _numeric()
    from camera3d_contracts import validate
    validate(optics,'optics');validate(render,'render')
    p = optics['projection']
    near,far = p['near_clip_m'],p['far_clip_m']
    aspect = render['width']*render['pixel_aspect']['numerator']/(render['height']*render['pixel_aspect']['denominator'])
    overscan = render['overscan']
    result = np.zeros((4,4))
    if p['type'] == 'perspective':
        width,height = p['sensor_width_mm'],p['sensor_height_mm']
        fit = p['sensor_fit']
        if fit == 'horizontal':
            height = width/aspect
        elif fit == 'vertical':
            width = height*aspect
        elif render['gate_fit'] == 'crop':
            width = min(width,height*aspect);height=width/aspect
        else:
            width = max(width,height*aspect);height=width/aspect
        result[0,0]=2*p['focal_length_mm']/(width*overscan)
        result[1,1]=2*p['focal_length_mm']/(height*overscan)
        result[0,2]=-2*p['shift_x']/overscan
        result[1,2]=-2*p['shift_y']/overscan
        result[2,2]=-(far+near)/(far-near)
        result[2,3]=-2*far*near/(far-near)
        result[3,2]=-1
    else:
        height=p['orthographic_height_m']*overscan;width=height*aspect
        result[0,0]=2/width;result[1,1]=2/height
        result[0,3]=2*p['shift_x']/overscan;result[1,3]=2*p['shift_y']/overscan
        result[2,2]=-2/(far-near);result[2,3]=-(far+near)/(far-near)
        result[3,3]=1
    return _matrix(result)


def project(point, world, projection, width, height):
    np, rig = _numeric()
    if type(width) is not int or type(height) is not int or width < 1 or height < 1:
        raise ValueError('camera3d raster dimensions must be positive integers')
    camera=np.linalg.inv(_matrix(world,rigid=True))@np.r_[rig.vector(point),1.]
    clip=_matrix(projection)@camera
    if abs(float(clip[3])) < 1e-12:
        raise ValueError('camera3d projective division is undefined')
    ndc=clip[:3]/clip[3]
    return {'pixel':[float((ndc[0]+1)*width/2),float((1-ndc[1])*height/2)],
            'ndc':ndc.tolist(),'depth_m':float(-camera[2]),
            'inside':bool(camera[2]<0 and np.all(ndc>=-1) and np.all(ndc<=1))}


def unproject(pixel, depth_ndc, world, projection, width, height):
    np, _ = _numeric()
    if (len(pixel)!=2 or not all(math.isfinite(x) for x in (*pixel,depth_ndc))
            or type(width) is not int or type(height) is not int or width<1 or height<1):
        raise ValueError('camera3d requires finite raster point and positive dimensions')
    clip=np.array([2*pixel[0]/width-1,1-2*pixel[1]/height,depth_ndc,1.])
    point=_matrix(world,rigid=True)@np.linalg.inv(_matrix(projection))@clip
    if abs(float(point[3]))<1e-12:
        raise ValueError('camera3d unprojection at infinity')
    return point[:3]/point[3]


def screen_ray(pixel, world, projection, width, height):
    _,rig=_numeric()
    near=unproject(pixel,-1,world,projection,width,height)
    far=unproject(pixel,1,world,projection,width,height)
    return near,rig.unit(far-near)


def validate_evaluated_matrices(value):
    np,_=_numeric()
    world=_matrix(value['world_matrix'],rigid=True)
    view=_matrix(value['view_matrix'],rigid=True)
    _matrix(value['projection_matrix'])
    if not np.allclose(view@world,np.eye(4),atol=1e-8):
        raise ValueError('camera3d view matrix must invert world matrix')
