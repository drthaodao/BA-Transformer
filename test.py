import os, argparse, sys, tqdm, logging, cv2
import torch
import torch.nn as nn
import numpy as np
from glob import glob
import torch.nn.functional as F
from medpy.metric.binary import hd, hd95, dc, jc, assd

parser = argparse.ArgumentParser()
parser.add_argument('--log_name', type=str)
parser.add_argument('--gpu', type=str, default='1')
parser.add_argument('--fold', type=str, default='0')
parser.add_argument('--layer', type=int, default=50)
parser.add_argument('--trans', type=int, default=1)
parser.add_argument('--point_pred', type=int, default=0)
parser.add_argument('--arch', type=str, default='Transformer')
parser.add_argument('--dataset', type=str, default='isbi2018')
parse_config = parser.parse_args()
print(parse_config)
os.environ['CUDA_VISIBLE_DEVICES'] = parse_config.gpu

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

if parse_config.dataset == 'isbi2018':
    from dataset.isbi2018 import norm01, myDataset
    dataset = myDataset(parse_config.fold, 'valid', aug=False)
elif parse_config.dataset == 'isbi2016':
    from dataset.isbi2016 import norm01, myDataset
    dataset = myDataset('test', aug=False)

if parse_config.arch is 'Transformer':
    if parse_config.trans == 1 and parse_config.point_pred == 1:
        from models.BAT import BAT
        model = BAT(1, parse_config.net_layer).cuda()
    elif parse_config.trans == 1 and parse_config.point_pred == 0:
        from models.Transformer_Seg import Transformer
        model = Transformer(1, parse_config.net_layer).cuda()
    else:
        from models.Base import DeepLabV3
        model = DeepLabV3(1, parse_config.net_layer).cuda()

dir_path = "./logs/{}/".format(parse_config.log_name)

from src.LoadModel import load_model

model = load_model(model, dir_path + 'model/best.pkl')

# logging
txt_path = os.path.join(dir_path + 'parameter.txt')
logging.basicConfig(filename=txt_path,
                    level=logging.INFO,
                    format='[%(asctime)s.%(msecs)03d] %(message)s',
                    datefmt='%H:%M:%S')
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def test():
    dice_value = 0

    test_loader = torch.utils.data.DataLoader(dataset,
                                              batch_size=4,
                                              pin_memory=True,
                                              drop_last=False,
                                              shuffle=False)

    def test():
        model.eval()
        num = 0

        dice_value = 0
        jc_value = 0
        hd95_value = 0
        assd_value = 0

        from tqdm import tqdm
        labels = []
        pres = []
        for batch_idx, batch_data in tqdm(enumerate(test_loader)):
            data = batch_data['image'].to(device).float()
            label = batch_data['label'].to(device).float()
            with torch.no_grad():
                if parse_config.arch == 'transfuse':
                    _, _, output = model(data)
                elif parse_config.point_pred == 0:
                    output = model(data)
                elif parse_config.point_pred == 1:
                    output, _ = model(data)
                output = torch.sigmoid(output)
                output = output.cpu().numpy() > 0.5
            label = label.cpu().numpy()
            assert (output.shape == label.shape)
            labels.append(label)
            pres.append(output)
        labels = np.concatenate(labels, axis=0)
        pres = np.concatenate(pres, axis=0)
        print(labels.shape, pres.shape)
        for _id in range(labels.shape[0]):
            dice_ave = dc(labels[_id], pres[_id])
            jc_ave = jc(labels[_id], pres[_id])
            try:
                hd95_ave = hd95(labels[_id], pres[_id])
                assd_ave = assd(labels[_id], pres[_id])
            except RuntimeError:
                num += 1
                hd95_ave = 0
                assd_ave = 0

            dice_value += dice_ave
            jc_value += jc_ave
            hd95_value += hd95_ave
            assd_value += assd_ave

        dice_average = dice_value / (labels.shape[0] - num)
        jc_average = jc_value / (labels.shape[0] - num)
        hd95_average = hd95_value / (labels.shape[0] - num)
        assd_average = assd_value / (labels.shape[0] - num)

        logging.info('Dice value of test dataset  : %f' % (dice_average))
        logging.info('Jc value of test dataset  : %f' % (jc_average))
        logging.info('Hd95 value of test dataset  : %f' % (hd95_average))
        logging.info('Assd value of test dataset  : %f' % (assd_average))

        print("Average dice value of evaluation dataset = ", dice_average)
        print("Average jc value of evaluation dataset = ", jc_average)
        print("Average hd95 value of evaluation dataset = ", hd95_average)
        print("Average assd value of evaluation dataset = ", assd_average)
        return dice_average

    test()
    return


if __name__ == '__main__':
    test()