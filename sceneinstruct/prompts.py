import json
import numpy as np
from scipy import stats
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Instruction:
    id: int
    description: str
    augment_method: str = None
    parent_id: int = None
    depth: int = None
    code: str = None

@dataclass
class InstructionWithMeta(Instruction):
    has_quantity_changed: bool = False

item_list = ["Robot", 
             "Kuka Robot", "Kuka Robot KR125", "Kuka Robot KR350", 
             "ABB Robot", "ABB Robot IRB6600", 
             "YASKAWA Robot", "YASKAWA Robot ma01800", 
             "Table", "Welding Table", "Turntable", 
             "Guarding", "Cabinet", "ValveStand", "Conveyor"]
item_probs = (item_probs := np.concatenate([
    [4],
    [2, 1, 1],
    [2, 2],
    [2, 2],
    [4, 2, 2],
    [2, 2, 2, 2],
]).astype(np.float32)) / item_probs.sum()

evol_base_prompt = f"""You are given a description of a workstation, which is used to build a scene in Process Simulate (PS).
Your objective is to rewrite it into a different version of the given description.
The rewritten description must be reasonable and must be understood and responded to by humans.
You should change the given description using the following method:
<method>
Do not set the vertical coordinate of the objects.
For directions, consider the front as the positive direction of the x-axis, the back as the negative direction of the x-axis, the left as the positive direction of the y-axis, and the right as the negative direction of the y-axis.
There can be at most one Guarding object in the scene. Do not set relative positions for the Guarding object.
You must keep the industrial production process as [welding] in #Rewritten Description#, do not add other industrial production processes.
The objects in the #Given Description# must be from the list: [{", ".join(item_list)}]
You should not make the #Rewritten Description# verbose, #Rewritten Description# can only add 10 to 20 words into #Given Description#.
'#Given Description#', '#Rewritten Description#', 'given description' and 'rewritten description' are not allowed to appear in #Rewritten Description#.
"""

evol_feedback_prompt = """Your rewritten description contains the following error:
```
{feedback}
```
Please rewrite the given description again, fixing the errors.
Return the rewritten description only."""

methods = [
    """Add or replace one or more objects in the #Given Description#. The objects must be chosen from: [{}].""",
    """Specify the locations of the objects mentioned in the #Given Description# on the ground in format [x, y, 0] with reasonable coordinate values in millimeters, which should be greater than -5000 and less than 5000. The Euclidean distance between objects should be greater than 1 meter and less than 5 meters. Keep the name of the objects.""",
    """Specify the relative position between two objects mentioned in #Given Description#. The relative position may include distance, direction, or orientation. The distance should have reasonable value in meters. The Euclidean distance between objects should be greater than 1 meter and less than 5 meters. Keep the name of the objects.""",
    """If there is an object that is not assigned with coordinates or relative positions, change its quantity in the #Given Description# to {}. Do not add other objects.""",
    """If there are two objects, replace the relative position description of them with a fuzzy expression, such as front, back, left, right, next to, and remove the numerical values. Do not add other objects.""",
    """Rewrite the #Given Description# with a similar meaning like an industrial engineer would. Keep the name of the objects.""",
]
method_weight = (method_weight := np.array([5, 6, 6, 1, 5, 1], dtype=np.float32)) / method_weight.sum()

item_numbers = np.arange(3, 10 + 1)
poisson_probs = stats.poisson.pmf(item_numbers, 4)
poisson_probs /= poisson_probs.sum()
item_num_dist = stats.rv_discrete(values=(item_numbers, poisson_probs))

def get_evol_input(given_prompt: InstructionWithMeta, evol_prompt_template: str, method=None):
    if not method:
        method_prob = method_weight.copy()
        if given_prompt.has_quantity_changed:
            method_prob[3] = 0
        method_prob /= method_prob.sum()
        method_id = int(np.random.choice(range(len(methods)), p=method_prob))
        method = methods[method_id]
        if method_id == 0:
            items = np.random.choice(item_list, np.random.randint(2, 5), p=item_probs, replace=False)
            method = method.format(", ".join(items))
        if method_id == 3:
            method = method.format(item_num_dist.rvs())
    else:
        method_id = -1
    prompt = evol_prompt_template.replace("<method>", method)
    prompt += "#Given Description#:\n{}\n".format(given_prompt.question)
    prompt += "#Rewritten Description#:\n"
    return prompt, method, method_id
