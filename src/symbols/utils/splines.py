from geomdl import BSpline, knotvector

def resample_by_arc_length(points: list[tuple[float, float]], sample_spacing: float = 0.01):
    """
    Resamples a set of coordinates based on inter-point distances, as the raw output of Bezier
    curve creation is often tighter in some areas and sparser in others
    """
    if len(points) < 2:
        return points

    segment_lengths = [
        ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        for a, b in zip(points, points[1:])
    ]
    total_length = sum(segment_lengths)

    if total_length == 0:
        return points

    sample_spacing = max(sample_spacing, 1e-6)
    resampled = [points[0]]
    segment_index = 0
    running_length = 0.0
    next_distance = sample_spacing

    while next_distance < total_length:
        while segment_index < len(segment_lengths) and running_length + segment_lengths[segment_index] < next_distance:
            running_length += segment_lengths[segment_index]
            segment_index += 1

        if segment_index >= len(segment_lengths):
            break

        segment_start = points[segment_index]
        segment_end = points[segment_index + 1]
        segment_length = segment_lengths[segment_index]

        if segment_length == 0:
            resampled.append(segment_end)
            next_distance += sample_spacing
            continue

        local_distance = next_distance - running_length
        ratio = local_distance / segment_length

        resampled.append((
            segment_start[0] + (segment_end[0] - segment_start[0]) * ratio,
            segment_start[1] + (segment_end[1] - segment_start[1]) * ratio,
        ))
        next_distance += sample_spacing

    # add final point back in
    if resampled[-1] != points[-1]:
        resampled.append(points[-1])

    return resampled

def get_spline_path_points(control_points:list[tuple[float,float]]):
    DEGREE=2
    SAMPLE_SPACING=0.01

    curve_points=control_points
    if len(control_points) > 2:
        curve = BSpline.Curve()
        curve.degree=DEGREE
        curve.ctrlpts=control_points
        curve.knotvector=knotvector.generate(DEGREE, len(control_points))
        curve.delta=0.005

        curve_points=curve.evalpts

    return resample_by_arc_length(curve_points, sample_spacing=SAMPLE_SPACING)