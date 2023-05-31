from spotsInYeasts.makeStats import make_histograms
from testing.testing import *
import sys

def main(argv):
    warning = "Expected arguments: utests, stats"
    if len(argv) <= 1:
        print(warning)
        return 0
    
    task = argv[1]
    print("Task: ", task)

    if task == "transmission":
        launch_test_transmission()
        return 0

    if task == "fluo":
        launch_test_fluo()
        return 0

    if task == "assembled":
        launch_assembled_test()
        return 0

    if task == "stats":
        make_histograms("/home/benedetti/Bureau/testing/assembled", "_measures.json", 100)
        return 0

    if task == "utests":
        sys.argv = sys.argv[0:1]
        unittest.main(verbosity=2)

    print(warning)
    return 1

main(sys.argv)
