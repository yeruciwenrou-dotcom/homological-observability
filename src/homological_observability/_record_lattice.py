"""Integer support and joint winding coordinates for a raw observation."""

from math import gcd

import networkx as nx
from sympy import Matrix
from sympy.matrices.normalforms import hermite_normal_form

from ._target_common import Budget, TargetLimits, matrix_to_dict, prepare
from .integer_lattice import IntegerImage, inclusion_coordinates


class RecordLattice:
    def __init__(self, model, target, reverse):
        budget = Budget(TargetLimits())
        basis, p, _, f = prepare(model, [target], (), budget, reverse)
        self.basis = basis
        self.readout_image = IntegerImage(p, budget)
        self.f = f
        self.step = gcd(*(int(x) for x in f * self.readout_image.kernel))
        self.names = [r.name for r in model.readouts]
        self.joint = f.col_join(p)
        self.image = hermite_normal_form(self.joint)
        budget.check("joint_image", self.image)
        self.coordinates = None
        if self.step and self.image.cols <= 2:
            self.coordinates = inclusion_coordinates(self.joint, self.image)
            budget.check("joint_coordinates", self.coordinates)

        # Integrating each cochain on the tree gives a vertex potential. Its
        # endpoint difference is known even for an open, partially observed path.
        tree = nx.Graph()
        tree.add_nodes_from(basis.vertices)
        tree.add_edges_from(basis.tree_edges)
        root = basis.vertices[0]
        self.potential = {root: Matrix.zeros(self.joint.rows, 1)}
        rows = [r.as_mapping() for r in (target, *model.readouts)]
        for u, v in nx.bfs_edges(tree, root):
            increment = Matrix(
                [row.get((u, v), 0) - row.get((v, u), 0) for row in rows]
            )
            self.potential[v] = self.potential[u] + increment

    def support(self, record):
        states = record["states"]
        values = Matrix(len(self.names), 1, [record["counts"][n] for n in self.names])
        offset = self.potential[states[-1]] - self.potential[states[0]]
        corrected = values - offset[1:, :]
        info = {
            "legal_record": None,
            "target_support": None,
            "endpoint_offset": [int(x) for x in offset],
            "corrected_counts": [int(x) for x in corrected],
            "joint_rank": self.image.cols,
        }
        # A single snapshot has zero elapsed time and permits the empty path only.
        if len(states) == 1:
            info["legal_record"] = not any(values)
            if info["legal_record"]:
                info["target_support"] = {"offset": 0, "step": 0}
            return info
        budget = Budget(TargetLimits())
        budget.check("legal_image", corrected)
        preimage, failed = self.readout_image.solve(corrected, budget)
        if failed is not None:
            info["failed_count_constraint"] = failed
        info["legal_record"] = preimage is not None
        if preimage is not None:
            base = int((self.f * preimage)[0] + offset[0])
            info["target_support"] = {
                "offset": base % self.step if self.step else base,
                "step": self.step,
            }
        return info

    def description(self):
        return {
            "tree_edges": [list(e) for e in self.basis.tree_edges],
            "chord_edges": [list(e) for e in self.basis.chord_edges],
            "joint_image_basis": matrix_to_dict(self.image),
            "chord_to_image_coordinates": None
            if self.coordinates is None
            else matrix_to_dict(self.coordinates),
        }
