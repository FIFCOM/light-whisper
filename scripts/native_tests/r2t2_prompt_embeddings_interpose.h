#pragma once

#include "engine/framework/core/backend.h"
#include <ggml-backend.h>

namespace engine::core {
ggml_status prompt_test_compute_backend_graph(
    ggml_backend_t backend, ggml_cgraph * graph,
    ggml_backend_graph_plan_t plan = nullptr, const char * label = nullptr);
}
void prompt_test_backend_tensor_get(const ggml_tensor * tensor, void * data, size_t offset, size_t size);

#define compute_backend_graph prompt_test_compute_backend_graph
#define ggml_backend_tensor_get prompt_test_backend_tensor_get
