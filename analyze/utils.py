import os
import sys
import time
import math
from functools import partial
from typing import Callable
import numpy as np
import torch
import torch.nn as nn
from timm.utils import AverageMeter
from timm.data.constants import IMAGENET_DEFAULT_MEAN, IMAGENET_DEFAULT_STD
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, RandomSampler
from collections import OrderedDict
import cv2


def import_abspy(name="models", path="classification/"):
    import sys
    import importlib
    path = os.path.abspath(path)
    assert os.path.isdir(path)
    sys.path.insert(0, path)
    module = importlib.import_module(name)
    sys.path.pop(0)
    return module


def get_dataset(root="./val", img_size=224, ret="", crop=True):
    from torch.utils.data import SequentialSampler, DistributedSampler, DataLoader
    size = int((256 / 224) * img_size) if crop else int(img_size)
    transform = transforms.Compose([
        transforms.Resize(size, interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.CenterCrop((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.25, 0.25, 0.25)),
    ])
    dataset = datasets.ImageFolder(root, transform=transform)
    if ret in dataset.classes:
        print(f"found target {ret}", flush=True)
        target = dataset.class_to_idx[ret]
        dataset.samples =  [s for s in dataset.samples if s[1] == target]
        dataset.targets = [s for s in dataset.targets if s == target]
        dataset.classes = [ret]
        dataset.class_to_idx = {ret: target}
    return dataset


def show_mask_on_image(img: torch.Tensor, mask: torch.Tensor, mask_norm=True):
    H, W, C = img.shape
    mH, mW = mask.shape
    mask = torch.nn.functional.interpolate(mask[None, None], (H, W), mode="bilinear")[0, 0]
    if mask_norm:
        mask = (mask - mask.min()) / (mask.max() - mask.min())
    img = img.clamp(min=0, max=1).cpu().numpy()
    mask = mask.clamp(min=0, max=1).cpu().numpy()
    heatmap = cv2.applyColorMap(np.uint8(255 * mask), cv2.COLORMAP_JET)
    # heatmap = np.float32(heatmap) / 255
    # cam = heatmap + np.float32(img)
    # cam = cam / np.max(cam)
    return heatmap
    return np.uint8(255 * cam)


class visualize:
    @staticmethod
    def get_colormap(name):
        import matplotlib as mpl
        """Handle changes to matplotlib colormap interface in 3.6."""
        try:
            return mpl.colormaps[name]
        except AttributeError:
            return mpl.cm.get_cmap(name)

    @staticmethod
    def visualize_attnmap(attnmap, savefig="", figsize=(18, 16), cmap=None, sticks=True, dpi=400, fontsize=35, imgori=None, alpha=1.0, colorbar=True, **kwargs):
        import matplotlib.pyplot as plt
        if isinstance(attnmap, torch.Tensor):
            attnmap = attnmap.detach().cpu().numpy()
        if isinstance(imgori, torch.Tensor):
            imgori = imgori.detach().cpu().numpy()
        plt.rcParams["font.size"] = fontsize
        plt.figure(figsize=figsize, dpi=dpi, **kwargs)
        ax = plt.gca()
        if imgori is not None:
            im = ax.imshow(imgori)
        im = ax.imshow(attnmap, cmap=cmap, alpha=alpha)
        # ax.set_title(title)
        if not sticks:
            ax.set_axis_off()
        if colorbar:
            cbar = ax.figure.colorbar(im, ax=ax)
        if savefig == "":
            plt.show()
        else:
            plt.savefig(savefig)
        plt.close()

    @staticmethod
    def visualize_attnmaps(attnmaps, savefig="", figsize=(18, 16), rows=1, cmap=None, dpi=400, fontsize=35, linewidth=2, **kwargs):
        # attnmaps: [(map, title), (map, title),...]
        import math
        import matplotlib.pyplot as plt
        vmin = min([np.min((a.detach().cpu().numpy() if isinstance(a, torch.Tensor) else a)) for a, t in attnmaps])
        vmax = max([np.max((a.detach().cpu().numpy() if isinstance(a, torch.Tensor) else a)) for a, t in attnmaps])
        cols = math.ceil(len(attnmaps) / rows)
        plt.rcParams["font.size"] = fontsize
        figsize=(cols * figsize[0], rows * figsize[1])
        fig, axs = plt.subplots(rows, cols, squeeze=False, sharex="all", sharey="all", figsize=figsize, dpi=dpi)
        for i in range(rows):
            for j in range(cols):
                idx = i * cols + j
                if idx >= len(attnmaps):
                    image = np.zeros_like(image)
                    title = "pad"
                else:
                    image, title = attnmaps[idx]
                if isinstance(image, torch.Tensor):
                    image = image.detach().cpu().numpy()
                im = axs[i, j].imshow(image, vmin=vmin, vmax=vmax, cmap=cmap)
                axs[i, j].set_title(title)
                axs[i, j].set_yticks([])
                axs[i, j].set_xticks([])
                print(title, "max", np.max(image), "min", np.min(image), end=" | ")
            print("")
        axs[0, 0].figure.colorbar(im, ax=axs)
        if savefig == "":
            plt.show()
        else:
            plt.savefig(savefig)
        plt.close()
        print("")

    @staticmethod
    def seanborn_heatmap(
        data, *,
        vmin=None, vmax=None, cmap=None, center=None, robust=False,
        annot=None, fmt=".2g", annot_kws=None,
        linewidths=0, linecolor="white",
        cbar=True, cbar_kws=None, cbar_ax=None,
        square=False, xticklabels="auto", yticklabels="auto",
        mask=None, ax=None,
        **kwargs
    ):
        from matplotlib import pyplot as plt
        from seaborn.matrix import _HeatMapper
        # Initialize the plotter object
        plotter = _HeatMapper(data, vmin, vmax, cmap, center, robust, annot, fmt,
                            annot_kws, cbar, cbar_kws, xticklabels,
                            yticklabels, mask)

        # Add the pcolormesh kwargs here
        kwargs["linewidths"] = linewidths
        kwargs["edgecolor"] = linecolor

        # Draw the plot and return the Axes
        if ax is None:
            ax = plt.gca()
        if square:
            ax.set_aspect("equal")
        plotter.plot(ax, cbar_ax, kwargs)
        mesh = ax.pcolormesh(plotter.plot_data, cmap=plotter.cmap, **kwargs)
        return ax, mesh

    @classmethod
    def visualize_snsmap(cls, attnmap, savefig="", figsize=(18, 16), cmap=None, sticks=True, dpi=80, fontsize=35, linewidth=2, **kwargs):
        import matplotlib.pyplot as plt
        if isinstance(attnmap, torch.Tensor):
            attnmap = attnmap.detach().cpu().numpy()
        plt.rcParams["font.size"] = fontsize
        plt.figure(figsize=figsize, dpi=dpi, **kwargs)
        ax = plt.gca()
        _, mesh = cls.seanborn_heatmap(attnmap, xticklabels=sticks, yticklabels=sticks, cmap=cmap, linewidths=0,
                center=0, annot=False, ax=ax, cbar=False, annot_kws={"size": 24}, fmt='.2f')
        cb = ax.figure.colorbar(mesh, ax=ax)
        cb.outline.set_linewidth(0)
        if savefig == "":
            plt.show()
        else:
            plt.savefig(savefig)
        plt.close()

    @classmethod
    def visualize_snsmaps(cls, attnmaps, savefig="", figsize=(18, 16), rows=1, cmap=None, sticks=True, dpi=80, fontsize=35, linewidth=2, **kwargs):
        # attnmaps: [(map, title), (map, title),...]
        import math
        import matplotlib.pyplot as plt
        vmin = min([np.min((a.detach().cpu().numpy() if isinstance(a, torch.Tensor) else a)) for a, t in attnmaps])
        vmax = max([np.max((a.detach().cpu().numpy() if isinstance(a, torch.Tensor) else a)) for a, t in attnmaps])
        cols = math.ceil(len(attnmaps) / rows)
        plt.rcParams["font.size"] = fontsize
        figsize=(cols * figsize[0], rows * figsize[1])
        fig, axs = plt.subplots(rows, cols, squeeze=False, sharex="all", sharey="all", figsize=figsize, dpi=dpi)
        for i in range(rows):
            for j in range(cols):
                idx = i * cols + j
                if idx >= len(attnmaps):
                    image = np.zeros_like(image)
                    title = "pad"
                else:
                    image, title = attnmaps[idx]
                if isinstance(image, torch.Tensor):
                    image = image.detach().cpu().numpy()
                _, im = cls.seanborn_heatmap(image, xticklabels=sticks, yticklabels=sticks, 
                                             vmin=vmin, vmax=vmax, cmap=cmap,
                                             center=0, annot=False, ax=axs[i, j], 
                                             cbar=False, annot_kws={"size": 24}, fmt='.2f')
                axs[i, j].set_title(title)
        cb = axs[0, 0].figure.colorbar(im, ax=axs)
        cb.outline.set_linewidth(0)
        if savefig == "":
            plt.show()
        else:
            plt.savefig(savefig)
        plt.close()


class EffectiveReceiptiveField:
    @staticmethod
    def simpnorm(data):
        data = np.power(data, 0.25)
        data = data / np.max(data)
        return data

    @staticmethod
    def get_rectangle(data, thresh):
        h, w = data.shape
        all_sum = np.sum(data)
        for i in range(1, h // 2):
            selected_area = data[h // 2 - i:h // 2 + 1 + i, w // 2 - i:w // 2 + 1 + i]
            area_sum = np.sum(selected_area)
            if area_sum / all_sum > thresh:
                return i * 2 + 1, (i * 2 + 1) / h * (i * 2 + 1) / w
        return None, None

    @staticmethod
    def get_input_grad(model, samples, square=True):
        outputs = model(samples)
        out_size = outputs.size()
        if square:
            assert out_size[2] == out_size[3]
        central_point = torch.nn.functional.relu(outputs[:, :, out_size[2] // 2, out_size[3] // 2]).sum()
        grad = torch.autograd.grad(central_point, samples)
        grad = grad[0]
        grad = torch.nn.functional.relu(grad)
        aggregated = grad.sum((0, 1))
        grad_map = aggregated.cpu().numpy()
        return grad_map

    @classmethod
    def get_input_grad_avg(cls, model: nn.Module, size=1024, data_path=".", num_images=50, norms=lambda x:x, mean=IMAGENET_DEFAULT_MEAN, std=IMAGENET_DEFAULT_STD):
        import tqdm
        from torchvision import datasets, transforms
        from torch.utils.data import DataLoader, RandomSampler
        transform = transforms.Compose([
            transforms.Resize(size, interpolation=transforms.InterpolationMode.BICUBIC),
            transforms.ToTensor(),
            transforms.Normalize(mean, std)
        ])
        dataset = datasets.ImageFolder(os.path.join(data_path, 'val'), transform=transform)
        data_loader_val = DataLoader(dataset, sampler=RandomSampler(dataset), pin_memory=True)

        meter = AverageMeter()
        model.cuda().eval()
        for _, (samples, _) in tqdm.tqdm(enumerate(data_loader_val)):
            if meter.count == num_images:
                break
            samples = samples.cuda(non_blocking=True).requires_grad_()
            contribution_scores = cls.get_input_grad(model, samples)
            if np.isnan(np.sum(contribution_scores)):
                print("got nan | ", end="")
                continue
            else:
                meter.update(contribution_scores)
        return norms(meter.avg)


class AttnMamba:
    @staticmethod
    @torch.no_grad()
    def attnmap_mamba(As, Bs, Cs, Ds, us, dts, delta_bias, mode="CB", ret="all", absnorm=0, scale=1, verbose=False):
        printlog = print if verbose else lambda *args, **kwargs: None
        printlog(As.shape, Bs.shape, Cs.shape, Ds.shape, us.shape, dts.shape, delta_bias.shape)
        print(f"attn for mode={mode}, ret={ret}, absnorm={absnorm}, scale={scale}", flush=True)

        _norm = lambda x: x
        if absnorm == 1:
            _norm = lambda x: ((x - x.min()) / (x.max() - x.min()))
        elif absnorm == 2:
            _norm = lambda x: (x.abs() / x.abs().max())

        B, G, N, L = Bs.shape
        GD, N = As.shape
        D = GD // G
        H, W = int(math.sqrt(L)), int(math.sqrt(L))
        mask = torch.tril(dts.new_ones((L, L)))
        dts = torch.nn.functional.softplus(dts + delta_bias[:, None]).view(B, G, D, L)
        dw_logs = As.view(G, D, N)[None, :, :, None] * dts[:,:,:,None,:] # (B, G, D, N, L)
        ws = torch.cumsum(dw_logs, dim=-1).exp()

        if mode == "CB":
            Qs, Ks = Cs[:,:,None,:,:], Bs[:,:,None,:,:]
        elif mode == "CBdt":
            Qs, Ks = Cs[:,:,None,:,:], Bs[:,:,None,:,:] * dts.view(B, G, D, 1, L)
        elif mode == "CwBw":
            Qs, Ks = Cs[:,:,None,:,:] * ws, Bs[:,:,None,:,:] / ws.clamp(min=1e-20)
        elif mode == "CwBdtw":
            Qs, Ks = Cs[:,:,None,:,:] * ws, Bs[:,:,None,:,:]  * dts.view(B, G, D, 1, L) / ws.clamp(min=1e-20)
        elif mode == "ww":
            Qs, Ks = ws, 1 / ws.clamp(min=1e-20)
        else:
            raise NotImplementedError

        printlog(ws.shape, Qs.shape, Ks.shape)
        printlog("Bs", Bs.max(), Bs.min(), Bs.abs().min())
        printlog("Cs", Cs.max(), Cs.min(), Cs.abs().min())
        printlog("ws", ws.max(), ws.min(), ws.abs().min())
        printlog("Qs", Qs.max(), Qs.min(), Qs.abs().min())
        printlog("Ks", Ks.max(), Ks.min(), Ks.abs().min())
        _Qs, _Ks = Qs.view(-1, N, L), Ks.view(-1, N, L)
        attns = (_Qs.transpose(1, 2) @ _Ks).view(B, G, -1, L, L)
        attns = attns.mean(dim=2) * mask

        attn0 = attns[:, 0, :].view(B, -1, L, L)
        attn1 = attns[:, 1, :].view(-1, H, W, H, W).permute(0, 2, 1, 4, 3).contiguous().view(B, -1, L, L)
        attn2 = attns[:, 2, :].view(-1, L, L).flip(dims=[-2]).flip(dims=[-1]).contiguous().view(B, -1, L, L)
        attn3 = attns[:, 3, :].view(-1, L, L).flip(dims=[-2]).flip(dims=[-1]).contiguous().view(B, -1, L, L)
        attn3 = attn3.view(-1, H, W, H, W).permute(0, 2, 1, 4, 3).contiguous().view(B, -1, L, L)

        # ao0, ao1, ao2, ao3: attntion in four directions without rearrange
        # a0, a1, a2, a3: attntion in four directions with rearrange
        # a0a2, a1a3, a0a1: combination of "a0, a1, a2, a3"
        # all: combination of all "a0, a1, a2, a3"
        if ret in ["ao0"]:
            attn = _norm(attns[:, 0, :]).view(B, -1, L, L).mean(dim=1)
        elif ret in ["ao1"]:
            attn = _norm(attns[:, 1, :]).view(B, -1, L, L).mean(dim=1)
        elif ret in ["ao2"]:
            attn = _norm(attns[:, 2, :]).view(B, -1, L, L).mean(dim=1)
        elif ret in ["ao3"]:
            attn = _norm(attns[:, 3, :]).view(B, -1, L, L).mean(dim=1)
        elif ret in ["a0"]:
            attn = _norm(attn0).mean(dim=1)
        elif ret in ["a1"]:
            attn = _norm(attn1).mean(dim=1)
        elif ret in ["a2"]:
            attn = _norm(attn2).mean(dim=1)
        elif ret in ["a3"]:
            attn = _norm(attn3).mean(dim=1)
        elif ret in ["all"]:
            attn = _norm((attn0 + attn1 + attn2 + attn3)).mean(dim=1)
        elif ret in ["nall"]:
            attn = (_norm(attn0) + _norm(attn1) + _norm(attn2) + _norm(attn3)).mean(dim=1) / 4.0
        else:
            raise NotImplementedError(f"{ret} is not allowed")
        attn = (scale * attn).clamp(max=attn.max())
        return attn[0]

    @staticmethod
    def convert_state_dict_from_mmdet(state_dict):
        new_state_dict = OrderedDict()
        for k in state_dict:
            if k.startswith("backbone."):
                new_state_dict[k[len("backbone."):]] = state_dict[k]
        return new_state_dict

    @staticmethod
    def checkpostfix(tag, value):
        ret = value[-len(tag):] == tag
        if ret:
            value = value[:-len(tag)]
        return ret, value

    @staticmethod
    def getdata(regs, device=None):
        As, Bs, Cs, Ds = -torch.exp(regs["A_logs"].to(torch.float32)), regs["Bs"], regs["Cs"], regs["Ds"]
        us, dts, delta_bias = regs["us"], regs["dts"], regs["delta_bias"]
        ys, oy = regs["ys"], regs["y"]
        print(As.shape, Bs.shape, Cs.shape, Ds.shape, us.shape, dts.shape, delta_bias.shape)
        B, G, N, L = Bs.shape
        GD, N = As.shape
        D = GD // G
        H, W = int(math.sqrt(L)), int(math.sqrt(L))
        if device is not None:
            As, Bs, Cs, Ds, us, dts, delta_bias, ys, oy = As.to(device), Bs.to(device), Cs.to(device), Ds.to(device), us.to(device), dts.to(device), delta_bias.to(device), ys.to(device), oy.to(device)

        return As, Bs, Cs, Ds, us, dts, delta_bias, ys, oy, B, G, N, D, H, W, L

    @classmethod
    @torch.no_grad()
    def get_attnmap_mamba(cls, ss2ds, stage=-1, mode="", verbose=False, raw_attn=False, block_id=0, scale=1, device=None):
        mode1 = mode.split("_")[-1]
        mode = mode[:-(len(mode1) + 1)]
        
        absnorm = 0
        tag, mode = cls.checkpostfix("_absnorm", mode)
        absnorm = 2 if tag else absnorm
        tag, mode = cls.checkpostfix("_norm", mode)
        absnorm = 1 if tag else absnorm
        print(mode1, absnorm)

        if raw_attn:
            As, Bs, Cs, Ds, us, dts, delta_bias, ys, oy, B, G, N, D, H, W, L = cls.getdata(getattr(ss2ds[stage][block_id], "__data__"), device=device)
            attn = cls.attnmap_mamba(As, Bs, Cs, Ds, us, dts, delta_bias, mode=mode1, ret=mode, absnorm=absnorm, verbose=verbose, scale=scale)
            return attn

        As, Bs, Cs, Ds, us, dts, delta_bias, ys, oy, B, G, N, D, H, W, L = cls.getdata(getattr(ss2ds[stage][0], "__data__"), device=device)
        allrolattn = torch.eye(L)
        for k in range(len(ss2ds[stage])):
            As, Bs, Cs, Ds, us, dts, delta_bias, ys, oy, B, G, N, D, H, W, L = cls.getdata(getattr(ss2ds[stage][k], "__data__"), device=device)
            attn = cls.attnmap_mamba(As, Bs, Cs, Ds, us, dts, delta_bias, mode=mode1, ret=mode, absnorm=absnorm, verbose=verbose, scale=scale)
            assert attn.shape == (L, L)
            assert attn.max() <= 1
            assert attn.min() >= 0
            rolattn = 0.5 * (attn.cpu() + torch.eye(L))
            rolattn = rolattn / rolattn.sum(-1)
            allrolattn = rolattn @ allrolattn
        return allrolattn
        


