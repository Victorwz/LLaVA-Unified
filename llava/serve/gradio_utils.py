import torch
import cv2
import io
import base64
from PIL import Image
from transformers import TextStreamer
from llava.constants import IMAGE_TOKEN_INDEX
from llava.conversation import conv_templates, SeparatorStyle
from llava.mm_utils import get_model_name_from_path, KeywordsStoppingCriteria, tokenizer_image_token
from llava.model.builder import load_pretrained_model
from llava.utils import disable_torch_init
from openai import OpenAI
client = OpenAI()

title_markdown = ("""
<div style="display: flex; justify-content: center; align-items: center; text-align: center;">
    <img src="https://z1.ax1x.com/2023/11/07/pil4sqH.png" alt="Video-LLaVA🚀" style="max-width: 120px; height: auto;">
  </a>
  <div>
    <h1> LaViA: Fine-Tuning Multimodal LLMs as Task Assistants with Video Instructions</h1>
  </div>
</div>
""")

block_css = """
#buttons button {
    min-width: min(120px,100%);
}
"""

tos_markdown = ("""
### Terms of use
By using this service, users are required to agree to the following terms:
The service is a research preview intended for non-commercial use only. It only provides limited safety measures and may generate offensive content. It must not be used for any illegal, harmful, violent, racist, or sexual purposes. The service may collect user dialogue data for future research.
Please click the "Flag" button if you get any inappropriate answer! We will collect those to keep improving our moderator.
For an optimal experience, please use desktop computers for this demo, as mobile devices may compromise its quality.
""")

learn_more_markdown = ("""
### License
The service is a research preview intended for non-commercial use only, subject to the model [License](https://github.com/facebookresearch/llama/blob/main/MODEL_CARD.md) of LLaMA, [Terms of Use](https://openai.com/policies/terms-of-use) of the data generated by OpenAI, and [Privacy Practices](https://chrome.google.com/webstore/detail/sharegpt-share-your-chatg/daiacboceoaocpibfodeljbdfacokfjb) of ShareGPT. Please contact us if you find any potential violation.
""")


class Chat:
    def __init__(self, model_path, conv_mode, model_base=None, load_8bit=False, load_4bit=False, device='cuda', cache_dir=None):
        disable_torch_init()
        model_name = get_model_name_from_path(model_path)
        self.tokenizer, self.model, processor, context_len = load_pretrained_model(model_path, model_base, model_name,
                                                                                   load_8bit, load_4bit,
                                                                                   device=device, cache_dir=cache_dir)
        self.image_processor = processor
        # self.video_processor = processor['video']
        self.conv_mode = conv_mode
        self.conv = conv_templates[conv_mode].copy()
        self.device = self.model.device
        print(self.model)

    def get_prompt(self, qs, state):
        state.append_message(state.roles[0], qs)
        state.append_message(state.roles[1], None)
        return state

    @torch.inference_mode()
    def generate(self, images_tensor: list, prompt: str, first_run: bool, state):
        tokenizer, model, image_processor = self.tokenizer, self.model, self.image_processor

        state = self.get_prompt(prompt, state)
        prompt = state.get_prompt()
        print(prompt)

        input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt').unsqueeze(0).to(self.device)

        max_new_tokens = 1024

        stop_str = self.conv.sep if self.conv.sep_style != SeparatorStyle.TWO else self.conv.sep2
        keywords = [stop_str]
        stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)
        # streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        # print(prompt, input_ids.shape, len(images_tensor), images_tensor[0].shape)
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=images_tensor,
                do_sample=False,
                temperature=1,
                max_new_tokens=128,
                # streamer=streamer,
                use_cache=True,
                stopping_criteria=[stopping_criteria])

        outputs = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]
        outputs = outputs.strip()
        if outputs.endswith(stop_str):
            outputs = outputs[:-len(stop_str)]
        outputs = outputs.strip()

        print('response', outputs)
        return outputs, state
    
    def process_video(self, video_path, return_tensors='pt'):
        def read_video(video_path):
            video = cv2.VideoCapture(video_path)

            base64Frames = []
            while video.isOpened():
                success, frame = video.read()
                if not success:
                    break
                _, buffer = cv2.imencode(".jpg", frame)
                base64Frames.append(base64.b64encode(buffer).decode("utf-8"))

            video.release()
            print(len(base64Frames), "frames read.")
            return base64Frames
        
        video_frames = read_video(video_path=video_path)
        image_tensors = []
        samplng_interval = int(len(video_frames) / 30)
        for i in range(0, len(video_frames), samplng_interval):
            rawbytes = base64.b64decode(video_frames[i])
            image = Image.open(io.BytesIO(rawbytes)).convert("RGB")
            image_tensor = self.image_processor.preprocess(image, return_tensors=return_tensors)['pixel_values'][0]
            image_tensors.append(image_tensor)
        
        return image_tensors


# class Chat:
#     def __init__(self, model_path, conv_mode, model_base=None, load_8bit=False, load_4bit=False, device='cuda', cache_dir=None):
#         disable_torch_init()
#         model_name = get_model_name_from_path(model_path)
#         self.tokenizer, self.model, processor, context_len = load_pretrained_model(model_path, model_base, model_name,
#                                                                                    load_8bit, load_4bit,
#                                                                                    device=device, cache_dir=cache_dir)
#         self.image_processor = processor
#         # self.video_processor = processor['video']
#         self.conv_mode = conv_mode
#         self.conv = conv_templates[conv_mode].copy()
#         self.device = self.model.device
#         print(self.model)

#     def get_prompt(self, qs, state):
#         state.append_message(state.roles[0], qs)
#         state.append_message(state.roles[1], None)
#         return state

#     @torch.inference_mode()
#     def generate(self, images_tensor: list, prompt: str, first_run: bool, state):
#         tokenizer, model, image_processor = self.tokenizer, self.model, self.image_processor

#         state = self.get_prompt(prompt, state)
#         prompt = state.get_prompt().replace("<image>\n", "").replace("<|end_of_text|>", "\n")
#         print(prompt)

#         # input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt').unsqueeze(0).to(self.device)

#         # temperature = 0.2

#         # max_new_tokens = 1024

#         # stop_str = self.conv.sep if self.conv.sep_style != SeparatorStyle.TWO else self.conv.sep2
#         # keywords = [stop_str]
#         # stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)
#         # # streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
#         # # print(prompt, input_ids.shape, len(images_tensor), images_tensor[0].shape)
#         # with torch.inference_mode():
#         #     output_ids = model.generate(
#         #         input_ids,
#         #         images=images_tensor,
#         #         do_sample=False,
#         #         temperature=1,
#         #         max_new_tokens=max_new_tokens,
#         #         # streamer=streamer,
#         #         use_cache=True,
#         #         stopping_criteria=[stopping_criteria])

#         # outputs = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]
#         # outputs = outputs.strip()
#         # if outputs.endswith(stop_str):
#         #     outputs = outputs[:-len(stop_str)]
#         # outputs = outputs.strip()

#         # print('response', outputs)

#         try:
#             PROMPT_MESSAGES = [
#                 {
#                     "role": "user",
#                     "content": [
#                         *map(lambda x: {"image": x, "resize": 768}, images_tensor),
#                         prompt,
#                     ],
#                 },
#             ]


#             params = {
#                 "model": "gpt-4o",
#                 "messages": PROMPT_MESSAGES,
#                 "max_tokens": 100,
#             }

#             result = client.chat.completions.create(**params)
#             outputs = result.choices[0].message.content
#             print(outputs)
#             return outputs, state
#         except Exception as e:
#             print(f"An error occurred: {e}")
#             return "Please try again", state
    
#     def process_video(self, video_path, return_tensors='pt'):
#         def read_video(video_path):
#             video = cv2.VideoCapture(video_path)

#             base64Frames = []
#             while video.isOpened():
#                 success, frame = video.read()
#                 if not success:
#                     break
#                 _, buffer = cv2.imencode(".jpg", frame)
#                 base64Frames.append(base64.b64encode(buffer).decode("utf-8"))

#             video.release()
#             print(len(base64Frames), "frames read.")
#             return base64Frames
        
#         video_frames = read_video(video_path=video_path)
#         image_tensors = []
#         samplng_interval = int(len(video_frames) / 30)
#         for i in range(0, len(video_frames), samplng_interval):
#             # rawbytes = base64.b64decode(video_frames[i])
#             # image = Image.open(io.BytesIO(rawbytes)).convert("RGB")
#             # image_tensor = self.image_processor.preprocess(image, return_tensors=return_tensors)['pixel_values'][0]
#             image_tensors.append(video_frames[i])

#         # image_tensor = self.image_processor.preprocess(video_frames[-1], return_tensors=return_tensors)['pixel_values'][0]
#         image_tensors.append(video_frames[-1])
#         return image_tensors

if __name__ == "__main__":
    conv_mode = "llama_3"
    model_path = 'weizhiwang/llava_llama3_8b_video'
    cache_dir = './cache_dir'
    device = 'cuda'
    load_8bit = True
    load_4bit = False
    dtype = torch.float16
    handler = Chat(model_path, conv_mode=conv_mode, device=device, cache_dir=cache_dir)


    state = conv_templates[conv_mode].copy()

    video = "/tmp/gradio/fde1f7a522299f7705d40a03d4c1516dcd6f0d21/sample_demo_1.mp4"
    images_tensor = []
    image_processor = handler.image_processor
    tensor = handler.process_video(video, return_tensors='pt')#['pixel_values'][0]
    # print(tensor.shape)
    tensor = [t.half().to(handler.model.device) for t in tensor]
    images_tensor += tensor
    text_en_in = '\n'.join(["<image>"] * len(images_tensor)) + '\n' + "Why this video is funny?"
    text_en_out, state_ = handler.generate(images_tensor, text_en_in, first_run=True, state=state)