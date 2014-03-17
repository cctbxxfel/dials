/*
 * reference_locator.cc
 *
 *  Copyright (C) 2013 Diamond Light Source
 *
 *  Author: James Parkhurst
 *
 *  This code is distributed under the BSD license, a copy of which is
 *  included in the root directory of this package.
 */
#include <boost/python.hpp>
#include <boost/python/def.hpp>
#include <boost/python/iterator.hpp>
#include <dials/algorithms/integration/profile/reference_locator.h>
#include <dials/algorithms/integration/profile/grid_sampler.h>
#include <dials/algorithms/integration/profile/xds_circle_sampler.h>
#include <dials/config.h>

namespace dials { namespace algorithms { namespace boost_python {

  using namespace boost::python;

  template <typename FloatType, typename ImageSampler>
  struct ReferenceLocatorPickleSuite : boost::python::pickle_suite {

    typedef ReferenceLocator<FloatType, ImageSampler> locator_type;

    static
    boost::python::tuple getinitargs(const locator_type &r) {
      return boost::python::make_tuple(r.profile(), r.mask(), r.sampler());
    }
  };

  template <typename FloatType, typename ImageSampler>
  ReferenceLocator<FloatType, ImageSampler>* make_reference_locator(
      af::versa< FloatType, scitbx::af::flex_grid<> > &profiles,
      af::versa< bool, scitbx::af::flex_grid<> > &masks,
      const ImageSampler &sampler_type) {
    af::versa< FloatType, af::c_grid<4> > profiles_c_grid(
      profiles.handle(), af::c_grid<4>(profiles.accessor()));
    af::versa< bool, af::c_grid<4> > masks_c_grid(
      masks.handle(), af::c_grid<4>(masks.accessor()));
    return new ReferenceLocator<FloatType, ImageSampler>(
      profiles_c_grid, masks_c_grid, sampler_type);
  }

  template <typename FloatType, typename ImageSampler>
  void reference_locator_wrapper(const char *name) {

    typedef FloatType float_type;
    typedef ImageSampler sampler_type;
    typedef ReferenceLocator<FloatType, ImageSampler> locator_type;

    af::versa<FloatType, af::c_grid<4> > (locator_type::*profile_all)() const =
      &locator_type::profile;
    af::versa<FloatType, af::c_grid<3> > (locator_type::*profile_at_index)(
      std::size_t) const = &locator_type::profile;
    af::versa<FloatType, af::c_grid<3> > (locator_type::*profile_at_coord)(
      double3) const = &locator_type::profile;

    af::versa<bool, af::c_grid<4> > (locator_type::*mask_all)() const =
      &locator_type::mask;
    af::versa<bool, af::c_grid<3> > (locator_type::*mask_at_index)(
      std::size_t) const = &locator_type::mask;
    af::versa<bool, af::c_grid<3> > (locator_type::*mask_at_coord)(
      double3) const = &locator_type::mask;

    double3 (locator_type::*coord_at_index)(
      std::size_t) const = &locator_type::coord;
    double3 (locator_type::*coord_at_coord)(
      double3) const = &locator_type::coord;

    class_<locator_type>(name, no_init)
      .def("__init__", make_constructor(
        &make_reference_locator<FloatType, ImageSampler>))
      .def("size", &locator_type::size)
      .def("sampler", &locator_type::sampler)
      .def("index", &locator_type::index)
      .def("indices", &locator_type::indices)
      .def("profile", profile_all)
      .def("profile", profile_at_index)
      .def("profile", profile_at_coord)
      .def("mask", mask_all)
      .def("mask", mask_at_index)
      .def("mask", mask_at_coord)
      .def("coord", coord_at_index)
      .def("coord", coord_at_coord)
      .def("correlations", &locator_type::correlations)
      .def("__len__", &locator_type::size)
      .def_pickle(ReferenceLocatorPickleSuite<float_type, sampler_type>());
  }

  void export_reference_locator()
  {
    reference_locator_wrapper<ProfileFloatType, GridSampler>(
      "GridReferenceLocator");
    reference_locator_wrapper<ProfileFloatType, XdsCircleSampler>(
      "XdsCircleReferenceLocator");
  }

}}} // namespace = dials::algorithms::boost_python
