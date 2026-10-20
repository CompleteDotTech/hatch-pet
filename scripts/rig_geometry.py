"""Non-destructive topology, measured bounds and explicit anatomical uncertainty."""
from __future__ import annotations

import numpy as np
from rig_errors import require
from rig_models import Geometry, Mesh, validate_geometry


def vertex_normals(positions: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    face = np.cross(positions[triangles[:, 1]] - positions[triangles[:, 0]],
                    positions[triangles[:, 2]] - positions[triangles[:, 0]])
    result = np.zeros_like(positions, dtype=np.float64)
    for i in range(3):
        np.add.at(result, triangles[:, i], face)
    length = np.linalg.norm(result, axis=1)
    result[length > 1e-12] /= length[length > 1e-12, None]
    result[length <= 1e-12] = [0, 1, 0]
    return result


def mesh_edges(triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    return np.unique(np.sort(edges, axis=1), axis=0, return_counts=True)


def connected_components(mesh: Mesh) -> list[np.ndarray]:
    parent = np.arange(len(mesh.positions))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return int(i)

    edges, _ = mesh_edges(mesh.triangles)
    for a, b in edges:
        a, b = root(a), root(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
    groups = {}
    for i in range(len(parent)):
        groups.setdefault(root(i), []).append(i)
    return [np.asarray(v, dtype=np.int64) for _, v in sorted(groups.items())]


def analyze_geometry(geometry: Geometry, limits=None) -> dict:
    validate_geometry(geometry, limits)
    bounds = np.array([[m.positions.min(axis=0), m.positions.max(axis=0)] for m in geometry.meshes])
    lower, upper = bounds[:, 0].min(axis=0), bounds[:, 1].max(axis=0)
    extent = upper-lower
    require(np.max(extent) > 1e-7, 'RIG_ZERO_GEOMETRY', 'Geometry has no measurable extent.')
    reports, total_area, center = [], 0., np.zeros(3)
    for mesh in geometry.meshes:
        v, t = mesh.positions, mesh.triangles
        cross = np.cross(v[t[:, 1]]-v[t[:, 0]], v[t[:, 2]]-v[t[:, 0]])
        areas = np.linalg.norm(cross, axis=1)/2
        edges, counts = mesh_edges(t)
        area = float(areas.sum())
        if area:
            center += (v[t].mean(axis=1)*areas[:, None]).sum(axis=0)
            total_area += area
        closed = bool(np.all(counts == 2))
        volume = float(np.sum(v[t[:, 0]]*np.cross(v[t[:, 1]], v[t[:, 2]]))/6) if closed else None
        reports.append(dict(id=mesh.id, vertices=len(v), triangles=len(t),
                            components=len(connected_components(mesh)), surface_area_m2=area,
                            boundary_edges=int(np.sum(counts == 1)), nonmanifold_edges=int(np.sum(counts > 2)),
                            degenerate_triangles=int(np.sum(areas < 1e-12)),
                            signed_volume_m3=volume, volume_status='measured-closed-surface' if closed else 'unavailable-open-surface',
                            bounds=[v.min(axis=0).tolist(), v.max(axis=0).tolist()], region=mesh.region))
    # Deterministic bounded sample for PCA and approximate X-plane symmetry.
    sample = np.concatenate([m.positions[::max(1, len(m.positions)//512)] for m in geometry.meshes])
    sample = sample[::max(1, len(sample)//2048)][:2048]
    mean = sample.mean(axis=0)
    eigenvalues, axes = np.linalg.eigh((sample-mean).T @ (sample-mean)/max(1, len(sample)))
    reflected = sample.copy(); reflected[:, 0] = lower[0]+upper[0]-reflected[:, 0]
    nearest = []
    for part in np.array_split(reflected, max(1, len(reflected)//128)):
        nearest.extend(np.sqrt(np.min(np.sum((part[:, None]-sample[None, :])**2, axis=2), axis=1)))
    return dict(schema_version=1, kind='hatch-3d-geometry-analysis', vertices=geometry.vertex_count,
                triangles=geometry.triangle_count, meshes=reports, bounds=[lower.tolist(), upper.tolist()],
                dimensions_m=extent.tolist(), surface_area_m2=total_area,
                surface_centroid_m=(center/total_area if total_area else mean).tolist(),
                center_of_mass_status='surface-area estimate; material density and interior are unknown',
                principal_axes=axes[:, ::-1].T.tolist(), principal_variance=eigenvalues[::-1].tolist(),
                symmetry_mean_error_m=float(np.mean(nearest)), symmetry_status='approximate geometry only; not anatomy approval',
                scale_status='canonical meters; source unit ambiguity requires explicit import scale',
                orientation_status='canonical orientation or explicit import conversion; PCA does not identify species')


def deformation_metrics(mesh: Mesh, deformed: np.ndarray) -> dict:
    require(deformed.shape == mesh.positions.shape and np.isfinite(deformed).all(),
            'RIG_NONFINITE_DEFORMATION', 'Deformation produced invalid vertices.', asset=mesh.id)
    edges, counts = mesh_edges(mesh.triangles)
    original_lengths = np.linalg.norm(mesh.positions[edges[:, 1]]-mesh.positions[edges[:, 0]], axis=1)
    new_lengths = np.linalg.norm(deformed[edges[:, 1]]-deformed[edges[:, 0]], axis=1)
    valid = original_lengths > 1e-9
    ratio = new_lengths[valid]/original_lengths[valid]
    t = mesh.triangles
    area = np.linalg.norm(np.cross(deformed[t[:, 1]]-deformed[t[:, 0]], deformed[t[:, 2]]-deformed[t[:, 0]]), axis=1)/2
    base_area = np.linalg.norm(np.cross(mesh.positions[t[:, 1]]-mesh.positions[t[:, 0]],
                                      mesh.positions[t[:, 2]]-mesh.positions[t[:, 0]]), axis=1)/2
    closed = bool(np.all(counts == 2))
    def volume(p): return float(np.sum(p[t[:, 0]]*np.cross(p[t[:, 1]], p[t[:, 2]]))/6)
    original_volume = abs(volume(mesh.positions)) if closed else 0
    return dict(max_vertex_displacement_m=float(np.linalg.norm(deformed-mesh.positions, axis=1).max()),
                max_edge_stretch=float(ratio.max()) if len(ratio) else 1.,
                min_edge_ratio=float(ratio.min()) if len(ratio) else 1.,
                newly_degenerate_triangles=int(np.sum((area < 1e-10) & (base_area > 1e-8))),
                volume_ratio=abs(volume(deformed))/original_volume if original_volume > 1e-9 else None,
                self_intersections='unavailable: no robust surface-intersection solver in the bounded core')
