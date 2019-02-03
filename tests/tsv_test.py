import inspect
import os
import sys
import unittest
from iterator import OffsetBounds
from tutils import Object
from typing import Any, Optional

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir + "/formats")
import tsv


class TestIterator(tsv.Iterator):
  def __init__(self, obj: Any, offset_bounds: Optional[OffsetBounds], adjust_chunk_size: int, read_chunk_size: int):
    self.adjust_chunk_size = adjust_chunk_size
    self.read_chunk_size = read_chunk_size
    tsv.Iterator.__init__(self, obj, offset_bounds)


class IteratorMethods(unittest.TestCase):
  def test_next(self):
    obj = Object("test.tsv", "A\tB\tC\na\tb\tc\n1\t2\t3\n")

    # Requires multiple passes
    it = TestIterator(obj, None, 11, 11)
    [items, offset_bounds, more] = it.next()
    self.assertEqual(list(items), ["A\tB\tC", "a\tb\tc"])
    self.assertEqual(offset_bounds, OffsetBounds(0, 11))
    self.assertTrue(more)

    [items, offset_bounds, more] = it.next()
    self.assertEqual(list(items), ["1\t2\t3"])
    self.assertEqual(offset_bounds, OffsetBounds(12, 17))
    self.assertFalse(more)

    # Read everything in one pass
    it = TestIterator(obj, None, 20, 20)
    [items, offset_bounds, more] = it.next()
    self.assertEqual(list(items), ["A\tB\tC", "a\tb\tc", "1\t2\t3"])
    self.assertEqual(offset_bounds, OffsetBounds(0, 17))
    self.assertFalse(more)

  def test_combine(self):
    object1 = Object("test1.tsv", "A\tB\tC\na\tb\tc\n1\t2\t3\n")
    object2 = Object("test2.tsv", "D\tE\tF\nd\te\tf\n4\t5\t6\n")
    object3 = Object("test3.tsv", "G\tH\tI\ng\th\ti\n7\t8\t9\n")
    object4 = Object("test4.tsv", "J\tK\tL\nj\tk\tl\n10\t11\t12\n")
    objects = [object1, object2, object3, object4]

    temp_name = "/tmp/ripple_test"
    with open(temp_name, "wb+") as f:
      tsv.Iterator.combine(objects, f)

    with open(temp_name) as f:
      self.assertEqual(f.read(), "A\tB\tC\na\tb\tc\n1\t2\t3\nD\tE\tF\nd\te\tf\n4\t5\t6\nG\tH\tI\ng\th\ti\n7\t8\t9\nJ\tK\tL\nj\tk\tl\n10\t11\t12\n")
    os.remove(temp_name)


if __name__ == "__main__":
  unittest.main()
