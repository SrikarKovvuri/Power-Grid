import numpy as np
import unittest
from sklearn.neighbors import NearestNeighbors

def get_k_nearest_neighbors(k, wildfire_positions, node_positions):
    neigh = NearestNeighbors(n_neighbors=k)
    neigh.fit(node_positions)
    distances, indices = neigh.kneighbors(wildfire_positions)
    return distances, indices

class TestKNearestNeighbors(unittest.TestCase):

    def test_get_k_nearest_neighbors(self):
        node_positions = np.array([
            [0, 0],
            [0, 2],
            [2, 0],
            [2, 2],
            [1, 1]
        ])
        wildfire_positions = np.array([
            [0.1, 0.1],
            [1.9, 1.9]
        ])
        k = 3
        expected_indices = [
            {0, 4, 2},
            {3, 4, 2}
        ]

        distances, indices = get_k_nearest_neighbors(k, wildfire_positions, node_positions)

        for i, index_set in enumerate(expected_indices):
            self.assertSetEqual(index_set, set(indices[i]))

if __name__ == '__main__':
    unittest.main()
