import sys
import os

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(parent_dir)

import utils

from tqdm import tqdm
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.utils
import matplotlib.pyplot as plt
import numpy as np

from audio_model import WaveNet,device,DilatedCausalConv,ResidualBlock

# aishell3 = utils.AISHELL3()
# train_loader = aishell3.train_loader
# valid_loader = aishell3.valid_loader
musicgenres = utils.MusicGenres(batch_size=10)
train_loader = musicgenres.train_loader
valid_loader = musicgenres.valid_loader

@torch.no_grad()
def sample(model:WaveNet,save_dir,init=False):
    batch = next(iter(valid_loader))
    token = batch.get('sources',(None,))[0]
    original_audio = batch['audios'][0]
    label = batch['labels'][0]
    assert os.path.exists('./samples')
    if init:
        utils.saveaudio(
            original_audio,
            sample_rate=11025,
            path=f'./samples/original_{musicgenres.GENRE_MAP[label.item()]}.wav'
        )
    model.eval()
    out_audio = model.generate(tokens=token,audio_leng=11025)
    utils.saveaudio(
        out_audio,
        sample_rate=11025,
        path=save_dir
    )

def visualize_receptive_field(model:WaveNet):
    foo = torch.zeros(1,2,11025).to(device)
    foo.requires_grad_(True)

    conv = DilatedCausalConv(2,2,11,padding=5,dilation=1).to(device)
    # res = ResidualBlock(2,1).to(device)

    # out = res(foo)
    out = conv(foo)
    # out = model(audio=foo)
    index = 1000
    out[...,index].sum().backward()
    # out[...,index,:].sum().backward()
    y = foo.grad[0,0].abs().cpu().numpy()
    plt.plot(y)
    # plot a straight line at index position
    plt.plot([index,index],[0,1],color='red')
    plt.xlim(990,1010)
    plt.show()
    plt.savefig(f'./receptive_field_{index}.png')

def train(epochs,model:WaveNet,optimizer,train_loader,valid_loader,eval_interval=1):
    for epoch in range(epochs):
        model.train()
        losses = []
        with tqdm(valid_loader) as bar:
            for i,batch in enumerate(bar):
                optimizer.zero_grad()
                tokens = None
                if 'sources' in batch:
                    tokens = batch['sources'].to(device)
                loss = model.get_loss(tokens=tokens,audio=batch['audios'].to(device))
                loss.backward()

                # test
                # print(list(model.modules()))
                # for module in model.modules():
                #     if isinstance(module,nn.Conv1d):
                #         print(module.weight.grad)
                #         print('\n'+'-'*10+'\n')
                        
                # exit()
                

                optimizer.step()
                losses.append(loss.item())
                # if i % 10 == 0:
                bar.set_description(f'Epoch {epoch}, Loss: {sum(losses[-10:])/len(losses[-10:]):.4f}')
        
        if epoch % eval_interval == 0:
            model.eval()
            losses = []
            with torch.no_grad():
                with tqdm(valid_loader) as bar:
                    for i,batch in enumerate(bar):
                        tokens = None
                        if 'sources' in batch:
                            tokens = batch['sources'].to(device)
                        loss = model.get_loss(tokens=tokens,audio=batch['audios'].to(device))
                        losses.append(loss.item())
                        if i % 10 == 0:
                            bar.set_description(f'[Eval],Epoch {epoch}, Loss: {sum(losses[-10:])/len(losses[-10:]):.4f}')


if __name__ == '__main__':    
    model = WaveNet(max_in_channel=2)
    model.to(device)
    # init parameters
    for p in model.parameters():
        if p.dim() > 1:
            nn.init.xavier_uniform_(p)
    utils.count_parameters(model)
    print(list(model.modules())[0])
    info = {
        'lr':1e-4,
        # 'weight_decay':0,
    }
    visualize_receptive_field(model)
    exit()
    optimizer = torch.optim.Adam(model.parameters(),**info)
    print('optimizer info:',info)
    os.makedirs('./samples',exist_ok=True)
    # sample(model,save_dir=os.path.join(f'./samples',f'init.wav'),init=True)
    train(100,model,optimizer,eval_interval=1,train_loader=train_loader,valid_loader=valid_loader)