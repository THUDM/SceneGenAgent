import gradio as gr
from layout_analysis import process_prompt
from code_gen import gen_code, show_complete_code
from model import LocalModel, GPT4O

def generate(text):
    # Set the models you want to use. Set to None to use the default model
    model_dict = {
        'default': LocalModel('<model-checkpoint-path>', base_url='http://localhost:8000/v1'),
        'retrieve_objects': None,
        'extract_layout': None,
        'assign_placement': LocalModel('assign_placement', base_url='http://localhost:8000/v1'),
        'check_positional_error': LocalModel('check_positional_error', base_url='http://localhost:8000/v1'),
        'fix_positional_error': LocalModel('fix_positional_error', base_url='http://localhost:8000/v1'),
        'generate_code': None,
        'fix_code': None
    }
    assert model_dict['default'] is not None
    model_default = model_dict['default']
    model_dict = {k: v if v else model_default for k, v in model_dict.items()}
    objects, placement, rewritten_prompt, _, _ = process_prompt(text,
        model_retrieve_objects=model_dict.get('retrieve_objects', model_default),
        model_extract_layout=model_dict.get('extract_layout', model_default),
        model_assign_placement=model_dict.get('assign_placement', model_default),
        model_check_positional_error=model_dict.get('check_positional_error', model_default),
        model_fix_positional_error=model_dict.get('fix_positional_error', model_default)
    )
    code, _ = gen_code(rewritten_prompt, objects, placement,
        model=model_default,
        model_generate_code=model_dict.get('generate_code', model_default),
        model_fix_code=model_dict.get('fix_code', model_default)
    )
    code = show_complete_code(code)
    return code

descriptions = [
    "Create a scene with multiple robots and cabinets and 3 worktables. Position 3 worktables with a 2.5-meter interval between each. Ensure that every table is closely accompanied by two robots and one cabinet.",
    "Create a layout featuring 6 robots positioned alongside two conveyor belts that are lined up end-to-end. Arrange 3 robots on each side of the conveyor belts in a straight line, with 1.5-meter intervals between each arm.",
    "I want a simulation scenario with the following layout: Position a welding table as the central element. Place a Kuka Robot KR125 2 meters in front of the table. To one side, at a distance of 4 meters from both the robot and table, arrange three cabinets in a row. Set the spacing between the first and second cabinet at 2.1 meters, and between the second and third cabinet at 1.3 meters.",
]

with gr.Blocks() as demo:
    gr.Markdown("## SceneGenAgent Demo")
    gr.Markdown("### Description")
    with gr.Row():
        prompt = gr.Textbox(
            label="Input Description",
            show_label=False,
            placeholder="Enter your description of the scene",
        )
            
        run_button = gr.Button("Generate Code", scale=0)

    examples = gr.Examples(descriptions, prompt)
    gr.Markdown("### Code")
    gr.Markdown("Run the code in [Process Simulate](https://plm.sw.siemens.com/en-US/tecnomatix/products/process-simulate-software/) to render the scene.")
    output = gr.Code(label='Code', interactive=False)

    run_button.click(
        generate, 
        inputs=[prompt], 
        outputs=[output]
    )

demo.launch()
