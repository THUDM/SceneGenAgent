import re
import json

##########
# Prompt #
##########

def contain_scalars(text):
    re_scalar = r'(?:^|\s)(\d+(\.\d+)?\s*m)'
    return bool(re.findall(re_scalar, text))

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
    should_filter, filter_reason = contain_positional_error(text, model)
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

########
# Code #
########

def contain_invalid_code(code):
    # custom place function
    if len(re.findall(r'double [\w\d]+ = x;', code)) > 0:
        return True, "Code contains invalid content '{}'".format(re.findall(r'double [\w\d]+ = x;', code))
    for ban_word in ['while ', 'class ', 'void ', '\nusing ', 'throw ', 'TxVector.Zero', 'TxVector.Identity', 'TxApplication.Output', 'PlaceRobot', 'PlaceObjectAt', 'CreateTransformation']:
        if ban_word in code:
            return True, f"Code contains invalid content '{ban_word}'"
    for ban_word in [r'^using ']:
        if re.findall(ban_word, code):
            return True, f"Code contains invalid content '{ban_word}'"
    return False, None

def miss_necessary_code(code):
    must_word = 'TxTransformation.TxRotationType.RPY_ZYX'
    if must_word not in code:
        return True, """You should use the following code to place objects:
```csharp
DirectoryInfo objModel1 = objModels[rand.Next(0, objModels.Count)];
string obj1Name = Path.GetFileNameWithoutExtension(objModel1.Name) + "_" + DateTime.Now.ToString("yyyy-MM-dd-HH-mm-ss");
TxInsertComponentCreationData txInsertDataObj1 = new TxInsertComponentCreationData(obj1Name, objModel1.FullName);
ITxComponent txComponentObject1 = txPhysicalRoot.InsertComponent(txInsertDataObj1);

double transXValue1 = x;
double transYValue1 = y;
double rotValue1 = degree * Math.PI / 180.0;
TxTransformation txTransTransXYRotZ = new TxTransformation(new TxVector(transXValue1, transYValue1, 0.0), new TxVector(0.0, 0.0, rotValue1), TxTransformation.TxRotationType.RPY_ZYX);
ITxLocatableObject obj1 = (ITxLocatableObject)txComponentObject1;
obj1.AbsoluteLocation *= txTransTransXYRotZ;
```
Do not use other methods made by yourself."""
    return False, None

def wrong_start(code):
    start_code = """string rootDir = TxApplication.SystemRootDirectory;
string weldingLibPath = Path.Combine(rootDir, "Welding");
string[] weldingModels = Directory.GetDirectories(weldingLibPath, "*.cojt", SearchOption.TopDirectoryOnly);"""
    if not code.startswith(start_code):
        return True, f"Code must start with:\n```csharp\n{start_code}\n```"
    return False, None

def filter_code(code, return_reason=False):
    assert code
    filter_reasons = []
    for func in [
        contain_invalid_code,
        miss_necessary_code,
        wrong_start,
    ]:
        should_filter, filter_reason = func(code)
        if should_filter:
            filter_reasons.append(filter_reason)
    should_filter = False
    filter_reason = None
    if len(filter_reasons) > 0:
        should_filter = True
        filter_reason = '\n'.join(filter_reasons)
    if return_reason:
        return should_filter, filter_reason
    return should_filter

def get_code_from_response(code):
    head = '```csharp\n'
    tail = '```'
    pos_head = code.find(head)
    if pos_head != -1:
        code = code[pos_head + len(head):]
        pos_tail = code.find(tail)
        if pos_tail != -1:
            code = code[:pos_tail]
    marker_start = 'string rootDir = TxApplication.SystemRootDirectory;'
    if code.find(marker_start) == -1:
        return ""
    pos_indents = -1
    lines = code.split('\n')
    lines_new = []
    for l in lines:
        if pos_indents == -1 and marker_start in l:
            pos_indents = l.find(marker_start)
        if pos_indents >= 0:
            if l.strip() == '' or l.startswith(' ' * pos_indents):
                lines_new.append(l[pos_indents:])
    return '\n'.join(lines_new)

def add_necessary_code(code):
    code = re.sub(r'^(//.*|\n)+', '', code)
    added_parts = []
    if not code.startswith("string rootDir = TxApplication.SystemRootDirectory;"):
        added_code = """string rootDir = TxApplication.SystemRootDirectory;

string weldingLibPath = Path.Combine(rootDir, "Welding");
string[] weldingModels = Directory.GetDirectories(weldingLibPath, "*.cojt", SearchOption.TopDirectoryOnly);

"""
        code = added_code + code.lstrip()
        added_parts.append(added_code)
        
    if 'Random rand = new Random();' not in code:
        added_code = "Random rand = new Random();\nTxPhysicalRoot txPhysicalRoot = TxApplication.ActiveDocument.PhysicalRoot;"
        code = code.replace("TxPhysicalRoot txPhysicalRoot = TxApplication.ActiveDocument.PhysicalRoot;", added_code)
        added_parts.append(added_code)
    
    code = re.sub(r'Console.Write(Line)?', 'output.Write', code)

    end_code = "TxApplication.RefreshDisplay();"
    end_pos = code.find(end_code)
    if end_pos != -1:
        code = code[:end_pos + len(end_code)]
    else:
        code = code.rstrip() + '\n\n' + end_code
        added_parts.append(end_code)
    return code, added_parts

def fix_obj_index(code):
    re_cond = r'(if \([\w\d]+\.Count >(=?\s*\d+\s*)\))'
    for cond, num in re.findall(re_cond, code):
        if num != ' 0':
            new_cond = cond.replace(num, ' 0')
            code = code.replace(cond, new_cond)
    re_idx = r'(DirectoryInfo [\w\d]+ = ([\w\d]+)(\[.*?\]);)'
    for line, lst, idx in re.findall(re_idx, code):
        new_idx = f'[rand.Next(0, {lst}.Count)]'
        if idx != new_idx:
            new_line = line.replace(idx, new_idx)
            code = code.replace(line, new_line)
    return code

def clean_code(code, return_history=False):
    clean_history = [["Original", code]]
    if not code:
        if return_history:
            return None, None
        return None
    code = get_code_from_response(code)
    if code != clean_history[-1][1]:
        clean_history.append(["Get code from response", code])
    code, added_parts = add_necessary_code(code)
    if len(added_parts) > 0:
        clean_history.append(["Added following code:\n{}".format("\n\n".join(added_parts)), code])
    code = fix_obj_index(code)
    if code != clean_history[-1][1]:
        clean_history.append(["Fix invalid index", code])
    if return_history:
        return code, clean_history
    return code
