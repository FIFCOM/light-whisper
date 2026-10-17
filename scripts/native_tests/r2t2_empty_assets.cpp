#include "engine/framework/assets/resource_bundle.h"

#include <utility>

// Frontend tests need only config-bearing empty assets, with no model IO.
// This is the upstream constructor body; no audio/DSP implementation is replaced.
namespace engine::assets {
ResourceBundle::ResourceBundle(std::filesystem::path model_root)
    : model_root_(std::move(model_root)) {}
}
