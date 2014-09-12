from __future__ import division

import iotbx.phil
from libtbx.utils import Sorry

master_phil_scope = iotbx.phil.parse("""
scan_range = None
  .help = "The range of images to use in indexing. Number of arguments"
          "must be a factor of two. Specifying \"0 0\" will use all images"
          "by default. The given range follows C conventions"
          "(e.g. j0 <= j < j1)."
  .type = ints(size=2)
  .multiple = True
first_n_reflections = None
  .type = int(value_min=0)
crystal_id = None
  .type = int
output {
  file_name = centroids.png
    .type = path
  show_plot = False
    .type = bool
  dpi = 300
    .type = int(value_min=0)
  size_inches = 10,10
    .type = floats(size=2, value_min=0)
  marker_size = 10
    .type = float(value_min=0)
}
""")

def run(args):
  if len(args) == 0:
    from libtbx.utils import Usage
    import libtbx.load_env
    from cStringIO import StringIO
    usage_message = """\
%s datablock.json reflections.pickle [options]

Parameters:
""" %libtbx.env.dispatcher_name
    s = StringIO()
    master_phil_scope.show(out=s)
    usage_message += s.getvalue()
    raise Usage(usage_message)
  from dials.util.command_line import Importer
  from scitbx.array_family import flex
  from scitbx import matrix
  from libtbx.phil import command_line
  importer = Importer(args, check_format=False)
  #assert len(importer.datablocks) == 1
  reflections = importer.reflections
  if importer.datablocks is not None and len(importer.datablocks) == 1:
    imageset = importer.datablocks[0].extract_imagesets()[0]
  elif importer.datablocks is not None and len(importer.datablocks) > 1:
    raise RuntimeError("Only one DataBlock can be processed at a time")
  elif len(importer.experiments.imagesets()) > 0:
    imageset = importer.experiments.imagesets()[0]
    imageset.set_detector(importer.experiments[0].detector)
    imageset.set_beam(importer.experiments[0].beam)
    imageset.set_goniometer(importer.experiments[0].goniometer)
  else:
    raise RuntimeError("No imageset could be constructed")
  #imageset = imagesets[0]
  #imageset = importer.datablocks[0].extract_imagesets()[0]
  detector = imageset.get_detector()
  scan = imageset.get_scan()
  args = importer.unhandled_arguments
  cmd_line = command_line.argument_interpreter(master_params=master_phil_scope)
  working_phil = cmd_line.process_and_fetch(args=args)
  params = working_phil.extract()
  panel_origin_shifts = {0: (0,0,0)}
  try:
    hierarchy = detector.hierarchy()
  except AttributeError, e:
    hierarchy = None
  for i_panel in range(1, len(detector)):
    origin_shift = matrix.col(detector[0].get_origin()) \
      - matrix.col(detector[i_panel].get_origin())
    panel_origin_shifts[i_panel] = origin_shift

  observed_xyz = flex.vec3_double()
  predicted_xyz = flex.vec3_double()

  for reflection_list in reflections:
    xyzcal_px = None
    xyzcal_px = None
    xyzobs_mm = None
    xyzcal_mm = None

    if 'xyzcal.px' in reflection_list:
      xyzcal_px = reflection_list['xyzcal.px']
    if 'xyzobs.px.value' in reflection_list:
      xyzobs_px = reflection_list['xyzobs.px.value']
    if 'xyzcal.mm' in reflection_list:
      xyzcal_mm = reflection_list['xyzcal.px']
    if 'xyzobs.mm.value' in reflection_list:
      xyzobs_mm = reflection_list['xyzobs.mm.value']

    if len(params.scan_range):
      sel = flex.bool(len(reflection_list), False)

      if xyzcal_px is not None and not xyzcal_px.norms().all_eq(0):
        centroids_frame = xyzcal_px.parts()[2]
      elif xyzobs_px is not None and not xyzobs_px.norms().all_eq(0):
        centroids_frame = xyzobs_px.parts()[2]
      else:
        raise Sorry("No pixel coordinates given in input reflections.")

      reflections_in_range = False
      for scan_range in params.scan_range:
        if scan_range is None: continue
        range_start, range_end = scan_range
        sel |= ((centroids_frame >= range_start) & (centroids_frame < range_end))
      reflection_list = reflection_list.select(sel)
    if params.first_n_reflections is not None:
      centroid_positions = reflection_list.centroid_position()
      centroids_frame = centroid_positions.parts()[2]
      perm = flex.sort_permutation(centroids_frame)
      perm = perm[:min(reflection_list.size(), params.first_n_reflections)]
      reflection_list = reflection_list.select(perm)
    if params.crystal_id is not None:
      reflection_list = reflection_list.select(
        reflection_list.crystal() == params.crystal_id)

    panel_ids = reflection_list['panel']
    if xyzobs_mm is None and xyzobs_px is not None:
      xyzobs_mm = flex.vec3_double()
      for i_panel in range(len(detector)):
        refls = reflection_list.select(panel_ids == i_panel)

        from dials.algorithms.centroid import centroid_px_to_mm_panel
        xyzobs_mm_panel, _, _ = centroid_px_to_mm_panel(
          detector[i_panel], scan, xyzobs_px,
          flex.vec3_double(xyzobs_px.size()),
          flex.vec3_double(xyzobs_px.size()))
        xyzobs_mm.extend(xyzobs_mm_panel)

    if xyzobs_mm is not None:
      observed_xyz.extend(xyzobs_mm)
    if xyzcal_mm is not None:
      predicted_xyz.extend(xyzcal_mm)

  obs_x, obs_y, _ = observed_xyz.parts()
  pred_x, pred_y, _ = predicted_xyz.parts()

  try:
    import matplotlib

    if not params.output.show_plot:
      # http://matplotlib.org/faq/howto_faq.html#generate-images-without-having-a-window-appear
      matplotlib.use('Agg') # use a non-interactive backend
    from matplotlib import pyplot
  except ImportError:
    raise Sorry("matplotlib must be installed to generate a plot.")

  fig = pyplot.figure()
  fig.set_size_inches(params.output.size_inches)
  fig.set_dpi(params.output.dpi)
  pyplot.axes().set_aspect('equal')
  marker_size = params.output.marker_size
  pyplot.scatter(obs_x, obs_y, marker='o', c='white', s=marker_size, alpha=1)
  pyplot.scatter(pred_x, pred_y, marker='+', s=marker_size, c='blue')
  #assert len(detector) == 1
  panel = detector[0]
  #if len(detector) > 1:
  xmin = max([detector[i_panel].get_image_size_mm()[0] + panel_origin_shifts[i_panel][0]
              for i_panel in range(len(detector))])
  xmax = max([detector[i_panel].get_image_size_mm()[0] + panel_origin_shifts[i_panel][0]
              for i_panel in range(len(detector))])
  ymax = max([detector[i_panel].get_image_size_mm()[1] + panel_origin_shifts[i_panel][1]
              for i_panel in range(len(detector))])
  ymax = max([detector[i_panel].get_image_size_mm()[1] + panel_origin_shifts[i_panel][1]
              for i_panel in range(len(detector))])
  if hierarchy is not None:
    beam_centre = hierarchy.get_beam_centre(imageset.get_beam().get_s0())
  else:
    beam_centre = detector[0].get_beam_centre(imageset.get_beam().get_s0())
  pyplot.scatter([beam_centre[0]], [beam_centre[1]], marker='+', c='blue', s=100)
  pyplot.xlim(0, xmax)
  pyplot.ylim(0, ymax)
  pyplot.gca().invert_yaxis()
  pyplot.title('Centroid x,y-coordinates')
  pyplot.xlabel('x-coordinate (mm)')
  pyplot.ylabel('y-coordinate (mm)')
  if params.output.file_name is not None:
    pyplot.savefig(params.output.file_name,
                   size_inches=params.output.size_inches,
                   dpi=params.output.dpi,
                   bbox_inches='tight')
  if params.output.show_plot:
    pyplot.show()


if __name__ == '__main__':
  import sys
  run(sys.argv[1:])
