// Optional CPython batch copier for qualified card metadata.
#include <pybind11/pybind11.h>

#include <unordered_map>
#include <vector>

namespace py = pybind11;

namespace {

struct Unsupported {};

// CPython 3.12 allocations can run cyclic GC. Guard the private traversal
// against callbacks mutating a list or dict while the borrowed items are read.
class PauseCyclicGC {
public:
    PauseCyclicGC() : was_enabled_(PyGC_Disable()) {}
    ~PauseCyclicGC() {
        if (was_enabled_) {
            PyGC_Enable();
        }
    }

private:
    const int was_enabled_;
};

bool exact_key(PyObject* value) {
    return PyUnicode_CheckExact(value) || PyLong_CheckExact(value)
        || PyFloat_CheckExact(value) || PyBool_Check(value) || value == Py_None;
}

class Batch {
public:
    Batch(const py::dict& memo, PyTypeObject* zone) : zone_(zone) {
        copies_.reserve(PyDict_Size(memo.ptr()));
        PyObject *key, *value;
        Py_ssize_t cursor = 0;
        while (PyDict_Next(memo.ptr(), &cursor, &key, &value)) {
            if (!PyLong_CheckExact(key)) {
                throw Unsupported{};
            }
            auto source = static_cast<PyObject*>(PyLong_AsVoidPtr(key));
            if (PyErr_Occurred()) {
                throw py::error_already_set();
            }
            copies_.emplace(source, py::reinterpret_borrow<py::object>(value));
        }
    }

    ~Batch() {
        if (completed_) {
            return;
        }
        // Discard partially built cycles without relying on the caller's GC.
        // Every pointer here is owned by copies_.
        for (auto* container : created_) {
            if (PyList_CheckExact(container)) {
                PyList_SetSlice(container, 0, PyList_GET_SIZE(container), nullptr);
            } else {
                PyDict_Clear(container);
            }
        }
    }

    py::tuple finish(const py::list& cards) {
        charge(PyList_GET_SIZE(cards.ptr()));
        py::list fields;
        for (Py_ssize_t i = 0; i < PyList_GET_SIZE(cards.ptr()); ++i) {
            auto* attributes = PyList_GET_ITEM(cards.ptr(), i);
            if (!PyDict_CheckExact(attributes)) {
                throw Unsupported{};
            }
            py::dict row;
            copy_items(attributes, row, true, 0);
            fields.append(row);
        }
        auto batch = py::make_tuple(fields, additions_, retained_);
        completed_ = true;
        return batch;
    }

private:
    void charge(Py_ssize_t size) {
        if (size > remaining_) {
            throw Unsupported{};
        }
        remaining_ -= size;
    }

    void remember(PyObject* source, const py::object& target) {
        copies_.emplace(source, target);
        created_.push_back(target.ptr());
        auto identity = py::reinterpret_steal<py::object>(PyLong_FromVoidPtr(source));
        if (!identity) {
            throw py::error_already_set();
        }
        additions_[identity] = target;
    }

    void copy_items(PyObject* source, py::dict& target, bool attributes, int depth) {
        charge(PyDict_GET_SIZE(source));
        PyObject *key, *value;
        Py_ssize_t cursor = 0;
        while (PyDict_Next(source, &cursor, &key, &value)) {
            if (!(attributes ? PyUnicode_CheckExact(key) : exact_key(key))) {
                throw Unsupported{};
            }
            auto child = copy(value, depth + 1);
            if (PyDict_SetItem(target.ptr(), key, child.ptr()) < 0) {
                throw py::error_already_set();
            }
        }
    }

    py::object copy(PyObject* source, int depth) {
        if (exact_key(source) || Py_TYPE(source) == zone_) {
            return py::reinterpret_borrow<py::object>(source);
        }
        if (const auto existing = copies_.find(source); existing != copies_.end()) {
            return existing->second;
        }
        if (depth > 128) {
            throw Unsupported{};
        }

        if (PyList_CheckExact(source)) {
            const auto count = PyList_GET_SIZE(source);
            charge(count);
            py::list target;
            remember(source, target);
            for (Py_ssize_t i = 0; i < count; ++i) {
                target.append(copy(PyList_GET_ITEM(source, i), depth + 1));
            }
            retained_.append(py::handle(source));
            return target;
        }
        if (PyDict_CheckExact(source)) {
            py::dict target;
            remember(source, target);
            copy_items(source, target, false, depth);
            retained_.append(py::handle(source));
            return target;
        }
        throw Unsupported{};
    }

    PyTypeObject* const zone_;
    Py_ssize_t remaining_ = 250000;
    bool completed_ = false;
    std::unordered_map<PyObject*, py::object> copies_;
    std::vector<PyObject*> created_;
    py::dict additions_;
    py::list retained_;
};

py::object copy_card_fields(const py::object& cards, const py::object& memo,
                            const py::object& zone) {
    if (!PyList_CheckExact(cards.ptr()) || !PyDict_CheckExact(memo.ptr())
            || !PyType_Check(zone.ptr())) {
        return py::none();
    }
    const PauseCyclicGC gc_guard;
    try {
        Batch batch(py::reinterpret_borrow<py::dict>(memo),
                    reinterpret_cast<PyTypeObject*>(zone.ptr()));
        return batch.finish(py::reinterpret_borrow<py::list>(cards));
    } catch (const Unsupported&) {
        return py::none();
    }
}

}  // namespace

PYBIND11_MODULE(_mtg_native_card_fields, module) {
    module.def("copy_card_fields", &copy_card_fields);
}
