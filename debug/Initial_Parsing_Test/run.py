"""Test for initial simple parameter parsing"""

from baybe.core import BayBE


# Simple example with one numerical target, two categorical and one numerical discrete
# parameter
config = {
    "Project_Name": "Initial Core Test",
    "Parameters": [
        {
            "Name": "Categorical_1",
            "Type": "CAT",
            "Values": [22, 33],
        },
        {
            "Name": "Categorical_2",
            "Type": "CAT",
            "Values": ["bad", "OK", "good"],
            "Encoding": "Integer",
        },
        {
            "Name": "Num_disc_1",
            "Type": "NUM_DISCRETE",
            "Values": [1, 2, 8],
            "Tolerance": 0.3,
        },
    ],
    "Objective": {
        "Mode": "SINGLE",
        "Targets": [{"Name": "Target_1", "Type": "NUM", "Bounds": None}],
    },
}

# Create BayBE object and print a summary
obj = BayBE(config=config)

print(obj)
