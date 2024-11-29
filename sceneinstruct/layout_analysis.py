import re
import json
import traceback
from typing import List
from cleaning import clean_prompt, contain_positional_error

def re_find(regex, text):
    return targets[0] if len(targets := re.findall(regex, text)) > 0 else None

### retrieve objects
prompt_fix_objects = """You are given a description of a workstation, which is used to build a scene in Process Simulate (PS).
The original description is as follows:
```
{prompt}
```
You should follow the steps below:
1. First, find all objects mentioned in the description and should appear in the workstation according to the description. Objects with or without specific positions should all be listed. If the description mentions multiple instances of the same object, list the object repeatedly for each instance. For example, if "ten tables" are mentioned, then include "table" ten times. Note that a "station", a "workstation", or a "scene" is not an object.
2. Then, fix the names of objects that are not correct. The objects that may appear in the description are from the permission list: [Kuka Robot KR125, Kuka Robot KR350, ABB Robot IRB6600, YASKAWA Robot ma01800, Welding Table, Turntable, Cabinet, ValveStand, Conveyor, Guarding]. For every object you find, change it so that it meets all the requirements:
   - All objects found in the previous step is independent of each other. Do not merge them into one object.
   - If the object is not from the permission list, including upper/lower cases, replace it with an object in the permission list that satisfies the restrictions in the description.
   - If there are objects with general types, replace them with specific objects from the list.
   - The object type must satisfy the restrictions in the description. For example, the description may state that some objects must be the same/different.
If the description requires you to add objects or there are no objects in the scene, add some objects that meet the description restrictions.
Only fix the objects that are already found and do not add additional objects.
Return all objects after correction, including ones that are correct and ones that are changed to be correct.
3. Finally, you should modify the original description:
   - Rewrite the description like an industrial modeling engineer would in accurate wordings.
   - Include all objects found in the last step, including upper/lower cases.
   - All objects found in the previous step is independent of each other. Do not merge them into one object.
   - Keep the positional, directional, and orientational information of objects.
   - Remove the color, shape, length, height, and function attributes of objects.
Return the rewritten description with one single sentence in one line and keep all positional information.

You should return your analysis, objects and description in the format below:
```
#Step 1: Find all objects#
Analysis: <analysis>
Objects: ["ObjA", "ObjB", ...]

#Step 2: Fix object names#
Analysis: <analysis>
Objects: ["ObjC", "ObjD", ...]

#Step 3: Rewrite description#
Analysis: <analysis>
New Description: <new description>
```
Do not say anything else."""

def list_objects(text, model_retrieve_objects):
    def parse_analysis(text):
        analysis = []
        re_steps = [
            r'#Step 1:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nObjects:',
            r'#Step 2:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nObjects:',
            r'#Step 3:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nNew Description:',
        ]
        step_names = ['Find all objects', 'Fix object names', 'Rewrite description']
        for re_step, step_name in zip(re_steps, step_names):
            as1 = re_find(re_step, text)
            if as1:
                analysis.append((step_name, as1))
        return analysis

    model_input = prompt_fix_objects.format(prompt=text)
    while True:
        text = model_retrieve_objects.generate(model_input)
        obj_lists = re.findall(r"Objects:\s*(\[.*?\])", text)
        descriptions = [l for l in re.findall(r'New Description:\s*([\s\S]*?)(?:$|`)', text)]
        if len(obj_lists) > 0 and len(descriptions) > 0:
            print("Objects:", text)
            print()
            analysis = parse_analysis(text)
            return obj_lists[-1], descriptions[-1], analysis, model_input, text

standard_item_name = """The objects in the description must be from the list: {item_list}.
If there are objects that are not in the above list, replace them with the most resembling objects from the list or remove it.
Remove the color and shape of objects.
Do not add objects into the description.
Only replace or remove the objects. Do not change other statements.
If there are no objects in the description, the rewritten description should be the same as the original description."""

### extract layout
prompt_extract_layout = """You are given a description of a workstation, which is used to build a scene in Process Simulate (PS).
The description includes several objects and their positions. The description is as follows:
```
{prompt}
```
The objects mentioned in the description are: {objects}
You should perform the following steps:
1. First, based on the provided object list, list all objects that are mentioned in the description and should appear in the scene according to the description. Objects with or without specific positions should all be listed.
If the description mentions multiple instances of the same object, list the object name repeatedly for each instance and assign numbers in the object names to tell them apart. There should be at most one Guarding in the scene.
You should return a list of objects in the following format:
```
Objects:
["ObjA", "ObjB 1", "ObjB 2", ...]
```
In the example, "ObjB 1" and "Obj 2" are two objects of the same kind. You should assign numbers to tell them apart.
You should not return unspecified object names. Instead, infer them to object names in the list.

2. Then, find all positional information of objects and reference points directly provided in the description. The positional information of objects include coordinates and orientations.
The coordinates are in the form of [x, y, 0], which should contain three values in millimeters in the form of "[x, y, 0]" with no unit after the brackets.
The coordinates of different objects must be different to avoid overlapping with Guarding as an exception, which surrounds the objects inside it and whose position represents its center which is not occupied.
For directions and orientations, consider the front as the positive direction of the x-axis, the back as the negative direction of the x-axis, the left as the positive direction of the y-axis, and the right as the negative direction of the y-axis.
The orientation of an object is what direction the object faces, including an angle rotated counterclockwise on the ground in degrees or towards other objects. For example, rotating for 0 degrees is to face the front, 90 degrees is to face the left, 180 degrees is to face the back, and 270 degrees is to face the right. The default orientation is to rotate for 0 degrees which makes the object face the positive direction of the x-axis.
Only list coordinates directly provided by the description. Do not calculate coordinates by yourself.
You should return a list of positions that appear in the description:
```json
Positions:
[
    {{
        "name": "<name>",
        "position": "<absolute position, including coordinate [x, y, 0]>",
        "orientation": "<orientation>"
    }},
    ...
]
```
Use JSON format. <name> should either be from the object list or be an reference point.
If no coordinates are provided, return an empty list.

3. Find every relative positions that are mentioned in the description between objects or reference points. The relative positions may include distances, directions, and orientations, and should include specific distances, directions, and orientations instead of ambiguous descriptions if they are provided. The distances between objects or reference points should be outside brackets and in meters. Each pair of objects or reference points should be listed at most once.
You should return a list of relative positions that appear in the description.
```json
Relative Positions:
[
    {{
        "object 1": "<name 1>",
        "relation": "<object 1 relative to object 2>",
        "object 2": "<name 2>"
    }},
    ...
]
```
Use JSON format. Both <name 1> and <name 2> should be either from the object list or an reference point.
If no relative positions are found, return an empty list.

You should first write your analysis of the description, then return the position information, in the following format:
```
#Step 1: Identify Objects#
Analysis: <analysis>
Objects:
[...]

#Step 2: Absolute Positions#
Analysis: <analysis>
Positions:
[
    ...
]

#Step 3: Relative Positions#
Analysis: <analysis>
Relative Positions:
[
    ...
]
```
Do not say anything else."""

def parse_placement(text):
    ocr = []
    for re_ocr in [
        r"#Step 1:[\s\S]+?\nObjects:\s*([\s\S]*?)\s*#Step 2",
        r"#Step 2:[\s\S]+?\nPositions:\s*([\s\S]*?)\s*#Step 3",
        r"#Step 3:[\s\S]+?\nRelative Positions:\s*([\s\S]*?)\s*(?:`|$)",
    ]:
        o = re.findall(re_ocr, text)
        if len(o) == 0:
            o = None
        else:
            o = o[0]
            startpos, endpos = o.find('['), o.rfind(']')
            o = None if startpos == -1 or endpos == -1 or startpos >= endpos else o[startpos:endpos + 1]
            if o:
                try:
                    json.loads(o)
                except:
                    o = None
        ocr.append(o)
    o, c, r = ocr[0], ocr[1], ocr[2]
    return o, c, r

def extract_layout(text, objects, model_extract_layout):
    def parse_analysis(text):
        analysis = []
        re_steps = [
            r'#Step 1:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nObjects:',
            r'#Step 2:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nPositions:',
            r'#Step 3:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nRelative Positions:',
        ]
        step_names = ['Identify Objects', 'Absolute Positions', 'Relative Positions']
        for re_step, step_name in zip(re_steps, step_names):
            as1 = re_find(re_step, text)
            if as1:
                analysis.append((step_name, as1))
        return analysis

    model_input = prompt_extract_layout.format(prompt=text, objects=objects)
    while True:
        model_output = model_extract_layout.generate(model_input)
        o, c, r = parse_placement(model_output)
        if o and c and r:
            print("Positions:", model_output)
            print()
            analysis = parse_analysis(model_output)
            return model_output, o, c, r, analysis, model_input

### assign placement
prompt_assign_placement = """You are given a description of a workstation wherein a series of objects exist, with their respective positions mentioned in the form of coordinates and relative positioning to one another. The description is as follows:
```
{prompt}
```
The objects mentioned in the description are: {objects}
Their known positions are as follows:
```
{coordinates}
```
Their relative positions are as follows:
```
{relations}
```
For directions and orientations, consider the front as the positive direction of the x-axis, the back as the negative direction of the x-axis, the left as the positive direction of the y-axis, and the right as the negative direction of the y-axis.
The orientation of an object is what direction the object faces, including an angle rotated counterclockwise on the ground in degrees or towards other objects. For example, rotating for 0 degrees is to face the front, 90 degrees is to face the left, 180 degrees is to face the back, and 270 degrees is to face the right.
Based on the description and position information, you should assign coordinates for every objects. The coordinates are three values in millimeters in the form of "[x, y, 0]" with no unit after the brackets, with x and y representing the components of the coordinate on the x-axis and y-axis respectively.
You should do the following:
1. Rewrite every relative position into the increment of one object's coordinate relative to another object's coordinate.
Write the increment in specific values [+-x, +-y, 0] instead of placeholders. One relative position should only be listed once.
If you need to set distances or directions yourself, the Euclidean distances between objects should generally be greater than 1 meter, which is 1000 in coordinates, unless stated otherwise in the description.
2. For each relative position, if one object has a declared coordinate, calculate the coordinate of the other object. Then, list the positional information of each object, including coordinates and orientations.
You should first perform calculations to get the coordinates in the analysis part, then come up with the final positions.
3. For the remaining objects without coordinates, assign valid coordinates for them based on the restrictions of object position, direction, orientation, and relation.
The coordinate values should generally be from [-5000, 0] or [0, 5000] intervals unless stated otherwise in the description.
The Euclidean distances between objects should generally be greater than 1 meter, which is 1000 in coordinates, unless stated otherwise in the description.
All objects are on the ground with no vertical relative positions.
To avoid overlapping, coordinates assigned in this step should be different from existing objects and each other, with the exception of Guarding which surrounds the objects and whose position represents its center which is not occupied.
You should first perform calculations to get the coordinates and deduce whether the coordinates of all objects meet the above conditions in the analysis part, then come up with the final positions.
After this step, every object in the description should have a coordinate.
You should list the positional information, including coordinates and orientations, of all objects in Step 3.
You must not skip any step.
You should return in the following format:
```
#Step 1: Rewrite Relative Position#
Analysis: <analysis>
New Relative Positions:
[
    {{
        "object 1": "<object name 1>",
        "relation": "[+-x, +-y, 0]",
        "object 2": "<object name 2>"
    }},
    ...
]

#Step 2: Calculate Coordinates#
Analysis: <analysis and calculation>
Positions:
[
    {{
        "name": "<object name>",
        "position": "[x, y, 0]",
        "orientation": "<orientation>"
    }},
    ...
]

#Step 3: Assign Positions#
Analysis: <analysis and calculation>
Positions:
[
    {{
        "name": "<object name>",
        "position": "[x, y, 0]",
        "orientation": "<orientation>"
    }},
    ...
]
```
Do not say anything else.
"""

permission_list = ["Kuka Robot KR125", "Kuka Robot KR350", "ABB Robot IRB6600", "YASKAWA Robot ma01800", "Welding Table", "Turntable", "Cabinet", "ValveStand", "Conveyor", "Guarding"]
def object_permitted(object):
    for p in permission_list:
        if p in object:
            return True
    return False

def parse_coordinates(text, coordinates):
    coords = []
    for re_coord in [
        r"#Step 2:[\s\S]+?\nPositions:\s*([\s\S]*?)\s*(?:`|#Step 3)",
        r"#Step 3:[\s\S]+?\nPositions:\s*([\s\S]*?)\s*(?:`|$)",
    ]:
        coord = re.findall(re_coord, text)
        if len(coord) == 0:
            coord = None
        else:
            coord = coord[0]
            startpos, endpos = coord.find('['), coord.rfind(']')
            coord = None if startpos == -1 or endpos == -1 or startpos >= endpos else coord[startpos:endpos + 1]
        coords.append(coord)
    coord_1, coord_2 = coords[0], coords[1]
    if coord_1 is None or coord_2 is None:
        return None
    try:
        coord_1, coord_2 = eval(coord_1.strip().replace('//', '#')), eval(coord_2.strip().replace('//', '#'))
        assert isinstance(coord_1, List) and isinstance(coord_2, List)
        coords = {}
        for cs in [json.loads(coordinates), coord_1, coord_2]:
            for c in cs:
                name = c.pop('name')
                if object_permitted(name):
                    coords[ name ] = c
        coords = [{"name": n, **p} for n, p in coords.items()]
        return coords
    except Exception as e:
        print(traceback.format_exc())
        return None

assign_coordinate_feedback_prompt = """Your position allocation contains the following error:
```
{feedback}
```
Please write the response again, fixing the errors.
Only generate the response. Do not say anything else."""

def assign_placement(prompt, objects, coordinates, relations, model):
    def parse_analysis(text):
        analysis = []
        re_steps = [
            r'#Step 1:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nNew Relative Positions:',
            r'#Step 2:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nPositions:',
            r'#Step 3:[\s\S]+?\nAnalysis:\s*([\s\S]*?)\s*\nPositions:',
        ]
        step_names = ['Rewrite Relative Position', 'Calculate Coordinates', 'Assign Coordinates']
        for re_step, step_name in zip(re_steps, step_names):
            as1 = re_find(re_step, text)
            if as1:
                analysis.append((step_name, as1))
        return analysis
    
    model_input_assign_placement = prompt_assign_placement.format(prompt=prompt, objects=objects, coordinates=coordinates, relations=relations)
    messages = [{
        "role": "user",
        "content": model_input_assign_placement
    }]
    coords_final = None
    failed_rounds = 0
    positional_error_list = []
    fix_error_list = []
    while True:
        try:
            # generate until valid coordinates appear
            while True:
                model_output_assign_placement = model.invoke(messages)
                coords = parse_coordinates(model_output_assign_placement, coordinates)
                if coords is not None:
                    print("Coordinates:", model_output_assign_placement)
                    analysis = parse_analysis(model_output_assign_placement)
                    break
            should_filter, filter_reason, model_input_check_positional_error, model_output_check_positional_error = contain_positional_error(prompt, coords, model)
            positional_error_list.append({
                "prompt": prompt,
                "coords": coords,
                "model_input": model_input_check_positional_error,
                "model_output": model_output_check_positional_error,
                "should_filter": should_filter,
                "filter_reason": filter_reason
            })
            if len(messages) > 1:
                fix_error_list.append({
                    "model_input": messages,
                    "model_output": model_output_assign_placement,
                    "is_last_round": not should_filter
                })
            if should_filter:
                failed_rounds += 1
                print("Filter reason:", filter_reason)
                print()
                new_messages = [
                    {"role": "assistant", "content": json.dumps(coords, indent=2)},
                    {"role": "user", "content": assign_coordinate_feedback_prompt.format(feedback=filter_reason)}
                ]
                messages = messages[:1]
                messages.extend(new_messages)
                continue
            print("Not filter reason:", filter_reason)
            coords_final = coords
            break
        except Exception as e:
            print(traceback.format_exc())
    return coords_final, model_output_assign_placement, analysis, failed_rounds, model_input_assign_placement, positional_error_list, fix_error_list

def retrieve_objects(prompt, model):
    objects, rewritten_prompt, analysis_list_objects, model_input, model_output = list_objects(prompt, model)
    rewritten_prompt_cleaned = clean_prompt(rewritten_prompt)
    model_output = model_output.replace(rewritten_prompt, rewritten_prompt_cleaned)
    return objects, rewritten_prompt_cleaned, analysis_list_objects, model_input, model_output

def get_placement(prompt, objects, model):
    analysis = []
    model_output_extract_layout, objects, coordinates, relations, analysis_extract_layout, model_input_extract_layout = extract_layout(prompt, objects, model)
    analysis.extend(analysis_extract_layout)
    coords, model_output_assign_placement, analysis_coordinates, failed_rounds, model_input_assign_placement, positional_error_list, fix_error_list = assign_placement(prompt, objects, coordinates, relations, model)
    analysis.extend(analysis_coordinates)
    return objects, coords, analysis, failed_rounds

def process_prompt(prompt, model):
    objects, rewritten_prompt, analysis_list_objects, model_input_rewrite_style, model_output_rewrite_style = retrieve_objects(prompt, model)
    objects, placement, analysis_get_placement, failed_rounds = get_placement(rewritten_prompt, objects, model)
    analysis = analysis_list_objects + analysis_get_placement
    return objects, placement, rewritten_prompt, analysis, failed_rounds
