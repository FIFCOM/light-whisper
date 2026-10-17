#pragma once
#include "engine/framework/core/backend.h"
#include <ggml-backend.h>

namespace engine::core {
ggml_status qwen_token_compute_graph(ggml_backend_t backend, ggml_cgraph * graph,
    ggml_backend_graph_plan_t plan = nullptr, const char * label = nullptr);
std::vector<float> qwen_token_read_f32(const ggml_tensor * tensor);
void qwen_token_read_f32_into(const ggml_tensor * tensor, std::vector<float> & values);
}
void qwen_token_tensor_get(const ggml_tensor * tensor, void * data, size_t offset, size_t size);

#define compute_backend_graph qwen_token_compute_graph
#define ggml_backend_tensor_get qwen_token_tensor_get
#define read_tensor_f32 qwen_token_read_f32
#define read_tensor_f32_into qwen_token_read_f32_into
