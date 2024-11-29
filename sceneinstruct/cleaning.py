import re
import json

##########
# Prompt #
##########

def contain_scalars(text):
    re_scalar = r'(?:^|\s)(\d+(\.\d+)?\s*m)'
    return bool(re.findall(re_scalar, text))

def contain_coords(text):
    re_coord = r'\[-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*\]'
    return bool(re.findall(re_coord, text))

def contain_numbers(text):
    re_coord = r'\[-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*\]'
    re_scalar = r'(?:^|\s)(\d+(\.\d+)?\s*m)'
    return bool(re.findall(re_coord, text)) or bool(re.findall(re_scalar, text))

def base_filter(text):
    if len(re.findall(r'[\u4e00-\u9fff]+', text)) > 0 or text == text.upper():
        return True, "The description should only contain English in proper upper and lower cases."
    return False, None

def vertical_nonzero(text):
    matches = re.findall(r'(\[[-\d\s.m]+\s*,\s*[-\d\s.m]+\s*,\s*([-\d\s.m]+)\])', text)
    for match in matches:
        if match[-1] not in ['0', '0.0', '0m', '0.0m', '0mm', '0.0mm']:
            return True, "The z-coordinates should be 0."
    return False, None

def contain_invalid_coordinate(text):
    matches = re.findall(r'(\[[^\[]+\s*,\s*[^\[]+\s*(,\s*[^\[]+)?\])', text)
    re_coord = r'^\[-?\d+(\.\d+)?\s*(m|mm)?\s*,\s*-?\d+(\.\d+)?\s*(m|mm)?\s*(,\s*-?\d+(\.\d+)?\s*(m|mm)?)?\]$'
    for match in matches:
        if not re.match(re_coord, match[0]):
            return True, "The coordinates should contain three values in millimeters in the form of [x, y, 0] with x and y being specific numbers."
    return False, None

def contain_ban_words(text):
    text = text.lower()
    ban_words = [re.findall(w, text)[0] for w in ['\n', 'without', 'instead', r'(?:\s|^)[nN]ot(?:\s|$|\.|,)', r'(?:\s|^)[nN]ow(?:\s|$|\.|,)', r'(?:\s|^)[nN]o(?:\s|$|\.|,)', 'east', 'west', 'north', 'south', 'workbench', 'euclid'] if len(re.findall(w, text)) > 0]
    if len(ban_words) > 0:
        return True, f"The description should not contain these words: {ban_words}"
    return False, None

check_relative_position_prompt = """You are given a description of a workstation, which is used to build a scene in Process Simulate (PS).
The description includes several objects and their positions. The description is as follows:
```
{prompt}
```
For directions and orientations, consider the front as the positive direction of the x-axis, the back as the negative direction of the x-axis, the left as the positive direction of the y-axis, and the right as the negative direction of the y-axis.
The orientation of an object is what direction the object faces, including an angle rotated counterclockwise on the ground in degrees or towards other objects. For example, rotating for 0 degrees is to face the front, 90 degrees is to face the left, 180 degrees is to face the back, and 270 degrees is to face the right. The default orientation is to rotate for 0 degrees which makes the object face the positive direction of the x-axis.
Based on the description, we allocate positions for the objects. The allocated positions of objects are as follows:
```
{positions}
```
However, the positions may represent certain errors which need to be identified.
You should carry out the following actions to check whether there are conflicts in object positions:
1. Calculate each object's positional arrangement. In case objects' positions are described relatively, deduce the corresponding coordinates. All objects exist in a 2D plane with z-coordinate being 0.
2. Identify any existing errors among the positions of the objects:
   - Constraints: The description may provide additional positional constraints which the objects should not violate. The front is the positive direction of the x-axis and the left is the positive direction of the y-axis.
   - Conflicts: The position description may contain inconsistencies among the objects. The position of an object may be calculated in many ways, and if the results obtained from different calculations are not consistent, there are conflicts in the description.
   - Overlap: The Euclidean distances between objects should be greater than 1 meter, which is 1000 in coordinates, or the objects will overlap with each other. Note that one exception is the Guarding, which surrounds the objects inside it and whose position represents its center which is not occupied. Also note that objects can overlap with each other if the description requires them to do so, e.g. their coordinates are explicitly specified.
3. Report whether there are positional errors. If you cannot deduce whether there are any errors - for example, when precise positions cannot be computed, please report that there are no errors.
You should return in the following format:
```
Relations: <Calculate the coordinates and positional relations>
Analysis: <Based on the calculated positions, deduce whether there are errors>
Error: <Based on the analysis, decide whether there are errors in the description. Choose between "Yes" and "No". If you can not determine, choose "No">
```
Do not say anything else.
"""

def contain_positional_error(text, positions, model):
    model_input = check_relative_position_prompt.format(prompt=text, positions=json.dumps(positions, indent=2))
    run_success = False
    for retry in range(5):
        model_output = model.generate(model_input)
        result = re.findall(r'\nError:.*?(Yes|No)', model_output)
        analysis = re.findall(r'(Relations:[\s\S]*?)\s*\nError:', model_output)
        if len(analysis) > 0 and len(result) > 0:
            run_success = True
            break
        print(model_output)
    if not run_success:
        return False, None, model_input, model_output
    result = result[0]
    analysis = analysis[0]
    return result == "Yes", analysis, model_input, model_output

prompt_check_relative_position_prompt = """You are given a description of a workstation, which is used to build a scene in Process Simulate (PS).
The description includes several objects and their positions. The description is as follows:
```
{prompt}
```

However, the positions in the description may represent certain errors which need to be identified.

You should carry out the following actions to check whether there are conflicts in object positions:

1. First, find all objects that are mentioned in the description and should appear in the scene according to the description.
The object names must be from the permission list: ["Robot", "Table", "Kuka Robot", "Welding Table", "Kuka Robot KR125", "YASKAWA Robot ma01800", "ABB Robot", "Turntable", "Kuka Robot KR350", "ABB Robot IRB6600", "YASKAWA Robot", "Cabinet", "ValveStand", "Conveyor", "Guarding"].
You should not return unspecified object names. Instead, infer them to specific object names in the list.
2. Calculate each object's positional arrangement. In case objects' positions are described relatively, deduce the corresponding coordinates. All objects exist in a 2D plane with z-coordinate being 0.
3. Identify any existing errors among the positions of the objects:
   - Constraints: The description may provide additional positional constraints which the objects should not violate.
   - Conflicts: The position description may contain inconsistencies among the objects. The position of an object may be calculated in many ways, and if the results obtained from different calculations are not consistent, there are conflicts in the description.
   - Overlap: The Euclidean distances between objects should be greater than 1 meter, which is 1000 in coordinates, or the objects will overlap with each other. Note that one exception is the Guarding, which surrounds the objects inside it and whose position represents its center which is not occupied.
4. Report whether there are errors in the description. If you cannot deduce whether there are any errors - for example, when precise positions cannot be computed, please report that there are no errors.

You should return in the following format:
```
Objects: <Objects>
Position: <Calculate the coordinates and positional relations>
Analysis: <Based on the calculated positions, deduce whether there are errors>
Error: <Based on the analysis, decide whether there are errors in the description. Choose between "Yes" and "No". If you can not determine, choose "No">
```

Do not say anything else.
"""
def prompt_contain_positional_error(text, model):
    model_input = prompt_check_relative_position_prompt.format(prompt=text.strip())
    run_success = False
    for retry in range(5):
        model_output = model.generate(model_input)
        result = re.findall(r'\nError:.*?(Yes|No)', model_output)
        analysis = re.findall(r'(Objects:[\s\S]*?)\s*\nError:', model_output)
        if len(analysis) > 0 and len(result) > 0:
            run_success = True
            break
        print(model_output)
    if not run_success:
        return False, None
    result = result[0]
    analysis = analysis[0]
    return result == "Yes", analysis

def filter_prompt(text, model):
    assert text
    filter_reasons = []
    for func in [
        base_filter,
        vertical_nonzero,
        contain_invalid_coordinate,
        contain_ban_words,
    ]:
        should_filter, filter_reason = func(text)
        if should_filter:
            filter_reasons.append(filter_reason)
    if len(filter_reasons) > 0:
        return True, '\n'.join(filter_reasons)
    should_filter, filter_reason = prompt_contain_positional_error(text, model)
    if should_filter:
        return True, filter_reason
    return False, None

def change_units(text):
    text = text.replace('(', '[').replace(')', ']')
    # remove mm unit outside coord
    matches = re.findall(r'(\[-?\d+(\.\d+)?,\s*-?\d+(\.\d+)?(,\s*-?\d+(\.\d+)?)?\]\s*(mm| millimeters))', text)
    for match in matches:
        value = match[0]
        value = re.sub(r'\s*mm', '', value).strip()
        value = re.sub(r'\s*millimeters', '', value).strip()
        text = text.replace(match[0], value)
    # convert [x m, y m] to [x * 1000, y * 1000]
    matches = re.findall(r'(\[(-?\d+(?:\.\d+)?)\s*m,\s*(-?\d+(?:\.\d+)?)\s*m\])', text)
    for match in matches:
        value = f"[{int(float(match[1]) * 1000)}, {int(float(match[2]) * 1000)}]"
        text = text.replace(match[0], value)
    # convert [x m, y m, z m] to [x * 1000, y * 1000, z * 1000]
    matches = re.findall(r'(\[(-?\d+(?:\.\d+)?)\s*m,\s*(-?\d+(?:\.\d+)?)\s*m,\s*(-?\d+(?:\.\d+)?)\s*m?\])', text)
    for match in matches:
        value = f"[{int(float(match[1]) * 1000)}, {int(float(match[2]) * 1000)}, {int(float(match[3]) * 1000)}]"
        text = text.replace(match[0], value)
    # remove mm unit inside coord
    matches = re.findall(r'(\[(-?\d+(?:\.\d+)?)\s*mm,\s*(-?\d+(?:\.\d+)?)\s*mm(,\s*(-?\d+(?:\.\d+)?)\s*mm)?\])', text)
    for match in matches:
        value = re.sub(r'\s*mm', '', match[0]).strip()
        text = text.replace(match[0], value)
    # replace cm with m in plain text
    matches = re.findall(r'(\d+(\.\d+)?\s*(?:cm|centimeters))', text)
    for match in matches:
        value = match[0]
        value = re.sub(r'cm|centimeters', '', value).strip()
        value = float(value) / 100
        text = text.replace(match[0], str(value) + ' meters')
    # add zero to z-axis
    matches = re.findall(r'(\[(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\])', text)
    for match in matches:
        value = match[0][:-1].rstrip() + ', 0]'
        text = text.replace(match[0], value)
    # change z-axis to zero
    matches = re.findall(r'(\[-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*(-?\d+(?:\.\d+)?\s*\]))', text)
    for match in matches:
        value = re.sub(match[1], '0]', match[0]).strip()
        text = text.replace(match[0], value)
    # reformat coords
    matches = re.findall(r'(\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\])', text)
    for match in matches:
        value = f"[{match[1]}, {match[2]}, {match[3]}]"
        text = text.replace(match[0], value)
    return text

def rule_clean(text):
    text = change_units(text)
    text = text.lstrip(".\"' ").rstrip("\"' ")
    text = text.replace('"', '').replace("'", "")
    return text.strip()

item_list = ["Robot", 
             "Kuka Robot", "Kuka Robot KR125", "Kuka Robot KR350", 
             "ABB Robot", "ABB Robot IRB6600", 
             "YASKAWA Robot", "YASKAWA Robot ma01800", 
             "Table", "Welding Table", "Turntable", "Turntable", 
             "Guarding", "Cabinet", "ValveStand", "Conveyor"]

def standardize_name(text):
    for item in item_list:
        text = re.sub(item, item, text, flags=re.IGNORECASE)
    return text.strip()

def clean_prompt(text):
    if not text:
        return None
    text = rule_clean(text)
    text = standardize_name(text)
    return text

standardize_name_template = f"""Your objective is to check whether a given prompt to meet certain standards.
The objects in the #Given Prompt# must be from the list: [{', '.join(item_list)}]. The first letters should be capitalized.
If any object in #Given Prompt# does not exist in the above list, replace it with the most resembling object from the list. Do not change anything else.
If every objects in #Given Prompt# are from the above list, #Rewritten Prompt# should be the same as the #Given Prompt#.
‘#Given Prompt#’, ‘#Rewritten Prompt#’, ‘given prompt’ and ‘rewritten prompt’ are not allowed to appear in #Rewritten Prompt#
"""

def standardize_name_model(text, model):
    model_input = standardize_name_template + "#Given Prompt#:\n{}\n".format(text) + "#Rewritten Prompt#:\n"
    try:
        model_output = model.generate(model_input)
        model_output = rule_clean(model_output)
        return model_output
    except:
        return text

def clean_prompt_model(text, model):
    assert text
    text = rule_clean(text)
    text = standardize_name_model(text, model)
    return text
