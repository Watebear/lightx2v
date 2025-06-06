import torch
from lightx2v.utils.registry_factory import (
    MM_WEIGHT_REGISTER,
    LN_WEIGHT_REGISTER,
    RMS_WEIGHT_REGISTER,
    TENSOR_REGISTER,
    ATTN_WEIGHT_REGISTER,
)
from lightx2v.common.modules.weight_module import WeightModule, WeightModuleList


class WanTransformerWeights(WeightModule):
    def __init__(self, config):
        super().__init__()
        self.blocks_num = config["num_layers"]
        self.task = config["task"]
        self.config = config
        if config["do_mm_calib"]:
            self.mm_type = "Calib"
        else:
            self.mm_type = config["mm_config"].get("mm_type", "Default") if config["mm_config"] else "Default"
        self.blocks = WeightModuleList([WanTransformerAttentionBlock(i, self.task, self.mm_type, self.config) for i in range(self.blocks_num)])
        self.add_module("blocks", self.blocks)


class WanTransformerAttentionBlock(WeightModule):
    def __init__(self, block_index, task, mm_type, config):
        super().__init__()
        self.block_index = block_index
        self.mm_type = mm_type
        self.task = task
        self.config = config
        self.quant_method = config["mm_config"].get("quant_method", None)
        self.sparge = config.get("sparge", False)
        self.register_parameter(
            "modulation",
            TENSOR_REGISTER["Default"](f"blocks.{self.block_index}.modulation"),
        )
        self.compute_phases = WeightModuleList(
            [
                WanSelfAttention(block_index, task, mm_type, config),
                WanCrossAttention(block_index, task, mm_type, config),
                WanFFN(block_index, task, mm_type, config),
            ]
        )

        self.add_module("compute_phases", self.compute_phases)

        # i2v


class WanSelfAttention(WeightModule):
    def __init__(self, block_index, task, mm_type, config):
        super().__init__()
        self.block_index = block_index
        self.mm_type = mm_type
        self.task = task
        self.config = config
        self.quant_method = config["mm_config"].get("quant_method", None)
        self.sparge = config.get("sparge", False)

        self.add_module(
            "self_attn_q",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.self_attn.q.weight",
                f"blocks.{self.block_index}.self_attn.q.bias",
            ),
        )
        self.add_module(
            "self_attn_k",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.self_attn.k.weight",
                f"blocks.{self.block_index}.self_attn.k.bias",
            ),
        )
        self.add_module(
            "self_attn_v",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.self_attn.v.weight",
                f"blocks.{self.block_index}.self_attn.v.bias",
            ),
        )
        self.add_module(
            "self_attn_o",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.self_attn.o.weight",
                f"blocks.{self.block_index}.self_attn.o.bias",
            ),
        )
        self.add_module(
            "self_attn_norm_q",
            RMS_WEIGHT_REGISTER["sgl-kernel"](f"blocks.{self.block_index}.self_attn.norm_q.weight"),
        )
        self.add_module(
            "self_attn_norm_k",
            RMS_WEIGHT_REGISTER["sgl-kernel"](f"blocks.{self.block_index}.self_attn.norm_k.weight"),
        )
        if self.sparge:
            assert self.config["sparge_ckpt"], "sparge_ckpt must be set when sparge is True"
            self.add_module(
                "self_attn_1",
                ATTN_WEIGHT_REGISTER["Sparge"](f"blocks.{self.block_index}"),
            )
            sparge_ckpt = torch.load(self.config["sparge_ckpt"])
            self.self_attn_1.load(sparge_ckpt)
        else:
            self.add_module("self_attn_1", ATTN_WEIGHT_REGISTER[self.config["attention_type"]]())
        if self.quant_method in ["smoothquant", "awq"]:
            self.register_parameter(
                "smooth_norm1_weight",
                TENSOR_REGISTER["Default"](f"blocks.{self.block_index}.affine_norm1.weight"),
            )
            self.register_parameter(
                "smooth_norm1_bias",
                TENSOR_REGISTER["Default"](f"blocks.{self.block_index}.affine_norm1.bias"),
            )


class WanCrossAttention(WeightModule):
    def __init__(self, block_index, task, mm_type, config):
        super().__init__()
        self.block_index = block_index
        self.mm_type = mm_type
        self.task = task
        self.config = config

        self.add_module(
            "norm3",
            LN_WEIGHT_REGISTER["Default"](
                f"blocks.{self.block_index}.norm3.weight",
                f"blocks.{self.block_index}.norm3.bias",
                eps=1e-6,
            ),
        )
        self.add_module(
            "cross_attn_q",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.cross_attn.q.weight",
                f"blocks.{self.block_index}.cross_attn.q.bias",
            ),
        )
        self.add_module(
            "cross_attn_k",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.cross_attn.k.weight",
                f"blocks.{self.block_index}.cross_attn.k.bias",
            ),
        )
        self.add_module(
            "cross_attn_v",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.cross_attn.v.weight",
                f"blocks.{self.block_index}.cross_attn.v.bias",
            ),
        )
        self.add_module(
            "cross_attn_o",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.cross_attn.o.weight",
                f"blocks.{self.block_index}.cross_attn.o.bias",
            ),
        )
        self.add_module(
            "cross_attn_norm_q",
            RMS_WEIGHT_REGISTER["sgl-kernel"](f"blocks.{self.block_index}.cross_attn.norm_q.weight"),
        )
        self.add_module(
            "cross_attn_norm_k",
            RMS_WEIGHT_REGISTER["sgl-kernel"](f"blocks.{self.block_index}.cross_attn.norm_k.weight"),
        )
        self.add_module("cross_attn_1", ATTN_WEIGHT_REGISTER[self.config["attention_type"]]())

        if self.config.task == "i2v":
            self.add_module(
                "cross_attn_k_img",
                MM_WEIGHT_REGISTER[self.mm_type](
                    f"blocks.{self.block_index}.cross_attn.k_img.weight",
                    f"blocks.{self.block_index}.cross_attn.k_img.bias",
                ),
            )
            self.add_module(
                "cross_attn_v_img",
                MM_WEIGHT_REGISTER[self.mm_type](
                    f"blocks.{self.block_index}.cross_attn.v_img.weight",
                    f"blocks.{self.block_index}.cross_attn.v_img.bias",
                ),
            )
            self.add_module(
                "cross_attn_norm_k_img",
                RMS_WEIGHT_REGISTER["sgl-kernel"](f"blocks.{self.block_index}.cross_attn.norm_k_img.weight"),
            )
            self.add_module("cross_attn_2", ATTN_WEIGHT_REGISTER[self.config["attention_type"]]())


class WanFFN(WeightModule):
    def __init__(self, block_index, task, mm_type, config):
        super().__init__()
        self.block_index = block_index
        self.mm_type = mm_type
        self.task = task
        self.config = config
        self.quant_method = config["mm_config"].get("quant_method", None)

        self.add_module(
            "ffn_0",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.ffn.0.weight",
                f"blocks.{self.block_index}.ffn.0.bias",
            ),
        )
        self.add_module(
            "ffn_2",
            MM_WEIGHT_REGISTER[self.mm_type](
                f"blocks.{self.block_index}.ffn.2.weight",
                f"blocks.{self.block_index}.ffn.2.bias",
            ),
        )

        if self.quant_method in ["smoothquant", "awq"]:
            self.register_parameter(
                "smooth_norm2_weight",
                TENSOR_REGISTER["Default"](f"blocks.{self.block_index}.affine_norm2.weight"),
            )
            self.register_parameter(
                "smooth_norm2_bias",
                TENSOR_REGISTER["Default"](f"blocks.{self.block_index}.affine_norm2.bias"),
            )
