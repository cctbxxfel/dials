#
# report.py
#
#  Copyright (C) 2013 Diamond Light Source
#
#  Author: James Parkhurst
#
#  This code is distributed under the BSD license, a copy of which is
#  included in the root directory of this package.
from __future__ import division
from dials.array_family import flex
from dials.array_family.flex import Binner


def flex_ios(val, var):
  '''
  Compute I/sigma or return zero for each element.

  '''
  assert(len(val) == len(var))
  result = flex.double(len(val),0)
  indices = flex.size_t(range(len(val))).select(var > 0)
  val = val.select(indices)
  var = var.select(indices)
  assert(var.all_gt(0))
  result.set_selected(indices, val / flex.sqrt(var))
  return result


def generate_integration_report(experiment, reflections, n_resolution_bins=20):
  '''
  Generate the integration report

  '''
  from collections import OrderedDict
  from dials.algorithms.statistics import pearson_correlation_coefficient
  from dials.algorithms.statistics import spearman_correlation_coefficient
  from cctbx import miller, crystal

  def overall_report(data):

    # Start by adding some overall numbers
    report = OrderedDict()
    report['n']           = len(reflections)
    report['n_full']      = data['full'].count(True)
    report['n_partial']   = data['full'].count(False)
    report['n_overload']  = data['over'].count(True)
    report['n_ice']       = data['ice'].count(True)
    report['n_summed']    = data['sum'].count(True)
    report['n_fitted']    = data['prf'].count(True)
    report['n_integated'] = data['int'].count(True)

    # Compute mean background
    try:
      report['mean_background'] = flex.mean(
        data['background.mean'].select(data['int']))
    except Exception:
      report['mean_background'] = 0.0

    # Compute mean I/Sigma summation
    try:
      report['ios_sum'] = flex.mean(
        data['intensity.sum.ios'].select(data['sum']))
    except Exception:
      report['ios_sum'] = 0.0

    # Compute mean I/Sigma profile fitting
    try:
      report['ios_prf'] = flex.mean(
        data['intensity.prf.ios'].select(data['prf']))
    except Exception:
      report['ios_prf'] = 0.0

    # Compute the mean profile correlation
    try:
      report['cc_prf'] = flex.mean(
        data['profile.correlation'].select(data['prf']))
    except Exception:
      report['cc_prf'] = 0.0

    # Compute the correlations between summation and profile fitting
    try:
      mask = data['sum'] & data['prf']
      Isum = data['intensity.sum.value'].select(mask)
      Iprf = data['intensity.prf.value'].select(mask)
      report['cc_pearson_sum_prf'] = pearson_correlation_coefficient(Isum, Iprf)
      report['cc_spearman_sum_prf'] = spearman_correlation_coefficient(Isum, Iprf)
    except Exception:
      report['cc_pearson_sum_prf'] = 0.0
      report['cc_spearman_sum_prf'] = 0.0

    # Return the overall report
    return report

  def binned_report(binner, index, data):

    # Create the indexers
    indexer_all = binner.indexer(index)
    indexer_sum = binner.indexer(index.select(data['sum']))
    indexer_prf = binner.indexer(index.select(data['prf']))
    indexer_int = binner.indexer(index.select(data['int']))

    # Add some stats by resolution
    report = OrderedDict()
    report['bins']         = list(binner.bins())
    report['n_full']       = list(indexer_all.sum(data['full']))
    report['n_partial']    = list(indexer_all.sum(~data['full']))
    report['n_overload']   = list(indexer_all.sum(data['over']))
    report['n_ice']        = list(indexer_all.sum(data['ice']))
    report['n_summed']     = list(indexer_all.sum(data['sum']))
    report['n_fitted']     = list(indexer_all.sum(data['prf']))
    report['n_integrated'] = list(indexer_all.sum(data['int']))

    # Compute mean background
    try:
      report['mean_background'] = list(indexer_int.mean(
        data['background.mean'].select(data['int'])))
    except Exception:
      report['mean_background'] = [0.0] * len(binner)

    # Compute mean I/Sigma summation
    try:
      report['ios_sum'] = list(indexer_sum.mean(
        data['intensity.sum.ios'].select(data['sum'])))
    except Exception:
      report['ios_sum'] = [0.0] * len(binner)

    # Compute mean I/Sigma profile fitting
    try:
      report['ios_prf'] = list(indexer_prf.mean(
        data['intensity.prf.ios'].select(data['prf'])))
    except Exception:
      report['ios_prf'] = [0.0] * len(binner)

    # Compute the mean profile correlation
    try:
      report['cc_prf'] = list(indexer_prf.mean(
        data['profile.correlation'].select(data['prf'])))
    except Exception:
      report['cc_prf'] = [0.0] * len(binner)

    # Return the binned report
    return report

  # Check the required columns are there
  assert("miller_index" in reflections)
  assert("d" in reflections)
  assert("flags" in reflections)
  assert("bbox" in reflections)
  assert("xyzcal.px" in reflections)
  assert("partiality" in reflections)
  assert("intensity.sum.value" in reflections)
  assert("intensity.sum.variance" in reflections)

  # Get the flag enumeration
  flags = flex.reflection_table.flags

  # Get some keys from the data
  data = {}
  for key in ['miller_index',
              'xyzcal.px',
              'd',
              'bbox',
              'background.mean',
              'partiality',
              'intensity.sum.value',
              'intensity.sum.variance',
              'intensity.prf.value',
              'intensity.prf.variance',
              'profile.correlation']:
    if key in reflections:
      data[key] = reflections[key]

  # Compute some flag stuff
  data["full"] = data['partiality'] > 0.997300203937
  data["over"] = reflections.get_flags(flags.overloaded)
  data["ice"] = reflections.get_flags(flags.in_powder_ring)
  data["sum"] = reflections.get_flags(flags.integrated_sum)
  data["prf"] = reflections.get_flags(flags.integrated_prf)
  data["int"] = reflections.get_flags(flags.integrated, all=False)

  # Try to calculate the i over sigma for summation
  data['intensity.sum.ios'] = flex_ios(
    data['intensity.sum.value'],
    data['intensity.sum.variance'])

  # Try to calculate the i over sigma for profile fitting
  try:
    data['intensity.prf.ios'] = flex_ios(
      data['intensity.prf.value'],
      data['intensity.prf.variance'])
  except Exception:
    pass

  # Create the crystal symmetry object
  cs = crystal.symmetry(
    space_group=experiment.crystal.get_space_group(),
    unit_cell=experiment.crystal.get_unit_cell())

  # Create the resolution binner object
  ms = miller.set(cs, data['miller_index'])
  ms.setup_binner(n_bins=n_resolution_bins)
  binner = ms.binner()
  brange = list(binner.range_used())
  bins = [binner.bin_d_range(brange[0])[0]]
  for i in brange:
    bins.append(binner.bin_d_range(i)[1])
  bins = flex.double(reversed(bins))
  resolution_binner = Binner(bins)

  # Create the frame binner object
  try:
    array_range = experiment.imageset.get_array_range()
  except:
    array_range = (0, len(experiment.imageset))
  frame_binner = Binner(flex.int(range(
    array_range[0],
    array_range[1]+1)).as_double())

  # Create the overall report
  overall = overall_report(data)

  # Create a report binned by resolution
  resolution = binned_report(resolution_binner, data['d'], data)

  # Create the report binned by image
  image = binned_report(frame_binner, data['xyzcal.px'].parts()[2], data)

  # Return the report
  return OrderedDict([
    ("overall", overall),
    ("resolution", resolution),
    ("image", image)])


class IntegrationReport(object):
  '''
  A class to store the integration report

  '''

  def __init__(self, experiments, reflections):
    '''
    Create the integration report

    :param experiments: The experiment list
    :param reflections: The reflection table

    '''
    from collections import OrderedDict

    # Split the tables by experiment id
    tables = reflections.split_by_experiment_id()
    assert(len(tables) == len(experiments))

    # Initialise the dictionary
    self._report = OrderedDict()
    self._report['integration'] = []

    # Generate an integration report for each experiment
    for i, (expr, data) in enumerate(zip(experiments, tables)):
      self._report['integration'].append(
        generate_integration_report(expr, data))

  def as_dict(self):
    '''
    Return the report as a dictionary

    :return: The report dictionary

    '''
    return self._report

  def as_str(self, prefix=''):
    '''
    Return the report as a string

    :return: The report string

    '''
    from libtbx.table_utils import format as table

    # Create the image table
    rows = [["Id",
             "Image",
             "# full",
             "# part",
             "# over",
             "# ice",
             "# sum",
             "# prf",
             "<Ibg>",
             "<I/sigI>\n (sum)",
             "<I/sigI>\n (prf)",
             "<CC prf>"]]
    for j, report in enumerate(self._report['integration']):
      report = report['image']
      for i in range(len(report['bins'])-1):
        rows.append([
          '%d'   % j,
          '%d'   % report['bins'][i],
          '%d'   % report['n_full'][i],
          '%d'   % report['n_partial'][i],
          '%d'   % report['n_overload'][i],
          '%d'   % report['n_ice'][i],
          '%d'   % report['n_summed'][i],
          '%d'   % report['n_fitted'][i],
          '%.2f' % report['mean_background'][i],
          '%.2f' % report['ios_sum'][i],
          '%.2f' % report['ios_prf'][i],
          '%.2f' % report['cc_prf'][i]])
    image_table = table(rows, has_header=True, justify='right', prefix=prefix)

    # Create the resolution table
    rows = [["Id",
             "d min",
             "# full",
             "# part",
             "# over",
             "# ice",
             "# sum",
             "# prf",
             "<Ibg>",
             "<I/sigI>\n (sum)",
             "<I/sigI>\n (prf)",
             "<CC prf>"]]
    for j, report in enumerate(self._report['integration']):
      report = report['resolution']
      for i in range(len(report['bins'])-1):
        rows.append([
          '%d'   % j,
          '%.2f' % report['bins'][i],
          '%d'   % report['n_full'][i],
          '%d'   % report['n_partial'][i],
          '%d'   % report['n_overload'][i],
          '%d'   % report['n_ice'][i],
          '%d'   % report['n_summed'][i],
          '%d'   % report['n_fitted'][i],
          '%.2f' % report['mean_background'][i],
          '%.2f' % report['ios_sum'][i],
          '%.2f' % report['ios_prf'][i],
          '%.2f' % report['cc_prf'][i]])
    resolution_table = table(rows, has_header=True, justify='right', prefix=prefix)

    # Create the overall table
    overall_tables = []
    for j, report in enumerate(self._report['integration']):
      report = report['overall']
      rows = [["number fully recorded",                 '%d'   % report["n_full"]],
              ["number partially recorded",             '%d'   % report["n_partial"]],
              ["number with overloaded pixels",         '%d'   % report["n_overload"]],
              ["number in powder rings",                '%d'   % report["n_ice"]],
              ["number processed with summation",       '%d'   % report["n_summed"]],
              ["number processed with profile fitting", '%d'   % report["n_fitted"]],
              ["<ibg>",                                 '%.2f' % report["mean_background"]],
              ["<i/sigi> (summation)",                  '%.2f' % report["ios_sum"]],
              ["<i/sigi> (profile fitting)",            '%.2f' % report["ios_prf"]],
              ["<cc prf>",                              '%.2f' % report["cc_prf"]],
              ["cc_pearson sum/prf",                    '%.2f' % report["cc_pearson_sum_prf"]],
              ["cc_spearman sum/prf",                   '%.2f' % report["cc_spearman_sum_prf"]]]
      overall_tables.append((j, table(rows, justify='left', prefix=prefix)))

    # Create the text
    text = [
      prefix + 'Summary vs image number',
      image_table,
      '\n',
      prefix + 'Summary vs resolution',
      resolution_table,
      '\n']
    for i, table in overall_tables:
      text.append(prefix + 'Summary for experiment %d' % i)
      text.append(table)
      text.append('\n')

    # Return the text
    return '\n'.join(text)