import pipeline
import unittest
from tutils import TestEntry, TestTable
from typing import Any, Dict
import os


class FaStore(unittest.TestCase):
  def test_basic(self):
    directory = os.path.dirname(os.path.realpath(__file__))
    os.chdir(directory)
    
    pp: pipeline.Pipeline = pipeline.Pipeline("fastore/fastore_compression.json")

    files = ["fastore_bin", "fastore_rebin", "fastore_pack","fastore_compress.sh"]

    pp.populate_table("jessie-fastore-program", "fastore/", files)

    name = "0/123.400000-13/1-1/1-1-1-fasta.fq"
    pp.run(name, "fastore/SP1.fq")

if __name__ == "__main__":
    unittest.main()
