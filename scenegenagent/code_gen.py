import os
import re
import json
import traceback
from copy import deepcopy
from termcolor import colored
from cleaning import filter_code, clean_code

code_gen_template = """You are given a description of a workstation, which is used to build a scene in Process Simulate (PS). You should write C# code with specific packages to build this scene.
The description is as follows:
```
{prompt}
```
The objects that should be added into the scene are as follows: {objects}
Their positions and orientations are as follows:
```
{positions}
```
You should write the complete code in the following format:
```csharp
string rootDir = TxApplication.SystemRootDirectory;
string weldingLibPath = Path.Combine(rootDir, "Welding");
string[] weldingModels = Directory.GetDirectories(weldingLibPath, "*.cojt", SearchOption.TopDirectoryOnly);

/* create model list */

foreach (string model in weldingModels)
{{
    DirectoryInfo directoryInfo = new DirectoryInfo(model);

    /* load models */
}}

Random rand = new Random();
TxPhysicalRoot txPhysicalRoot = TxApplication.ActiveDocument.PhysicalRoot;

/* add objects into the scene */

TxApplication.RefreshDisplay();
```
where the parts surrounded by "/* */" are the parts you should fill.

For the "create model list" part, you should define Lists of DirectoryInfo, which are used to store models in the "add models" part. For example, if you want a list to store robots:
```csharp
List<DirectoryInfo> robotModels = new List<DirectoryInfo>();
```
You can name the model lists whatever you like in a similar form.

For the "load models" part, you should check whether the current `directoryInfo` belongs to the types of models that are needed in the scene one by one and add it to corresponding model list.
You should use the following methods to load the objects:
{guidance_obj}

For the "add objects into the scene" part, you should add the objects into the scene and set its positions. For each object in the scene, pick the model from the model lists, put it into the scene, and set its coordinate and orientation.
To pick an object `obj1` from the list `objModels`, place it at [`x`, `y`, 0], and rotate it for `degree` degrees:
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

Now, you should generate the complete code to build this scene. Only generate the complete code. Your code will be run directly in the production environment, so don't omit anything.
Please strictly follow the given code snippets to load and place objects. Do not generate a class or a function, instead directly generate the function body. Do not define or call custom classes or functions by yourself.
Please use .NET Framework 4.6.2 or below, or the code will not run.
Do not say anything else.
"""

def read_file_tree(directory):
    file_tree = {}
    for root, dirs, files in os.walk(directory):
        current_node = file_tree
        for dir_name in root[len(directory):].split(os.path.sep):
            current_node = current_node.setdefault(dir_name, {})
        
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if file_name.endswith('.txt'):
                file_name = file_name[:-4]
                with open(file_path, 'r', encoding='utf-8') as file:
                    current_node[file_name] = file.read().strip()
    return file_tree['']

examples = read_file_tree('guidance')
examples_lower_case = deepcopy(examples)
examples_lower_case['object'] = {k.lower(): v for k, v in examples_lower_case['object'].items()}

def build_code_gen_prompt(prompt, objects, positions):
    guidances_obj = []
    objects_pos = [o['name'] for o in positions]
    for o in objects_pos:
        o_lower = re.sub('\s+\d+$', '', o).lower()
        if o_lower in examples_lower_case['object']:
            guidances_obj.append(examples_lower_case['object'][o_lower])
    guidance_obj = '\n'.join(guidances_obj)
    p = code_gen_template.format(prompt=prompt, objects=objects, positions=json.dumps(positions, indent=2), guidance_obj=guidance_obj)
    return p

code_feedback_prompt = """Your code contains the following error:
```
{feedback}
```
Please write the code again, fixing the errors.
Only generate the code. Do not say anything else."""

def gen_code(prompt, objects, placement, model, model_generate_code: str = None, model_fix_code: str = None):
    code_final = None
    code_gen_prompt = build_code_gen_prompt(prompt, objects, placement)
    messages = [{
        "role": "user",
        "content": code_gen_prompt
    }]
    failed_rounds = 0
    while failed_rounds < 5:
        try:
            model_output = model.invoke(messages).strip()
            model_output = clean_code(model_output)
            should_filter, filter_reason = filter_code(model_output, return_reason=True)
            if should_filter:
                failed_rounds += 1
                print(colored(f"Prompt: {json.dumps([code_gen_prompt])}", 'red') + f"Code: {[model_output]}" + f"\nFilter reason: {[filter_reason]}")
                new_messages = [
                    {"role": "assistant", "content": model_output},
                    {"role": "user", "content": code_feedback_prompt.format(feedback=filter_reason)}
                ]
                messages = messages[:1]
                messages.extend(new_messages)
                continue
            code_final = model_output
            break
        except Exception as e:
            print(traceback.format_exc())
            continue
    if code_final is None:
        code_final = model_output
    return code_final, failed_rounds

def show_complete_code(code):
    template = """using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using Tecnomatix.Engineering;

public class MainScript
{{
    public static void MainWithOutput(ref StringWriter output)
    {{
{code}
    }}
}}
"""
    lines = [f'        {line}' for line in code.rstrip().split('\n')]
    lines = '\n'.join(lines)
    code_preview = template.format(code=lines)
    return code_preview
