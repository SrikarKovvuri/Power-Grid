# tests/test_app.py
import unittest
from app import haversine

class TestApp(unittest.TestCase):
    
   def test_haversine(self):
    # Test with known values
    lon1, lat1 = 21.0122287, 52.2296756
    lon2, lat2 = 12.5113300, 41.8919300
    result = haversine(lon1, lat1, lon2, lat2)
    expected = 1315.607246 # expected distance between points in km
    self.assertAlmostEqual(result, expected, delta = 0.1)


if __name__ == '__main__':
    unittest.main()
