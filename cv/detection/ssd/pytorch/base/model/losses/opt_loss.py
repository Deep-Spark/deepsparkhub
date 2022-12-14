import torch

class OptLoss(torch.jit.ScriptModule):
    """
        Implements the loss as the sum of the followings:
        1. Confidence Loss: All labels, with hard negative mining
        2. Localization Loss: Only on positive labels
        Suppose input dboxes has the shape 8732x4
    """

    def __init__(self):
        super(OptLoss, self).__init__()

        self.sl1_loss = torch.nn.SmoothL1Loss(reduce=False)
        # Two factor are from following links
        # http://jany.st/post/2017-11-05-single-shot-detector-ssd-from-scratch-in-tensorflow.html
        self.con_loss = torch.nn.CrossEntropyLoss(reduce=False)

    @torch.jit.script_method
    def forward(self, ploc, plabel, gloc, glabel):
        """
            ploc, plabel: Nx4x8732, Nxlabel_numx8732
                predicted location and labels

            gloc, glabel: Nx4x8732, Nx8732
                ground truth location and labels
        """

        mask = glabel > 0
        pos_num = mask.sum(dim=1)

        # sum on four coordinates, and mask
        sl1 = self.sl1_loss(ploc, gloc).sum(dim=1)
        sl1 = (mask.type_as(sl1) * sl1).sum(dim=1)

        # hard negative mining
        con = self.con_loss(plabel, glabel)

        # postive mask will never selected
        con_neg = con.clone()
        # con_neg[mask] = 0
        con_neg.masked_fill_(mask, 0)
        # con_neg[con_neg!=con_neg] = 0
        con_neg.masked_fill_(con_neg!=con_neg, 0)
        con_s, con_idx = con_neg.sort(dim=1, descending=True)
        r = torch.arange(0, con_neg.size(1), dtype=torch.long, device='cuda').expand(con_neg.size(0), -1)
        con_rank = r.scatter(1, con_idx, r)

        # number of negative three times positive
        neg_num = torch.clamp(3*pos_num, max=mask.size(1)).unsqueeze(-1)
        neg_mask = con_rank < neg_num

        closs = (con*(mask.type_as(con_s) + neg_mask.type_as(con_s))).sum(dim=1)

        # avoid no object detected
        total_loss = sl1 + closs
        num_mask = (pos_num > 0).type_as(closs)
        pos_num = pos_num.type_as(closs).clamp(min=1e-6)
        ret = (total_loss * num_mask / pos_num).mean(dim=0)
        return ret
