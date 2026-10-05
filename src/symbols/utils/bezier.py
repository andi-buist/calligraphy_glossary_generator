def pascal_row(n):
            """
            Returns the nth row of Pascal's triangle to solve the generalized Bezier Curve formula
            """
            result = [1]
            x, numerator = 1, n
            for denominator in range(1, n//2+1):
                # print(numerator,denominator,x)
                x *= numerator
                x /= denominator
                result.append(x)
                numerator -= 1
            if n&1 == 0:
                # n is even
                result.extend(reversed(result[:-1]))
            else:
                result.extend(reversed(result))
            return result

def make_bezier(coords: list[tuple[float,float]]) -> list[tuple[float,float]]:
    """
    Makes a list of bezier coordinates for a set of input control coordinates
    """
    n = len(coords)
    combinations = pascal_row(n-1)
    def bezier(ts):
        # this uses the generalized formula for bezier curves
        # http://en.wikipedia.org/wiki/B%C3%A9zier_curve#Generalization
        result: list[tuple[float,float]] = []
        for t in ts:
            tpowers = (t**i for i in range(n))
            upowers = reversed([(1-t)**i for i in range(n)])
            coefs = [c*a*b for c, a, b in zip(combinations, tpowers, upowers)]
            result.append(
                tuple(sum([coef*p for coef, p in zip(coefs, ps)]) for ps in zip(*coords)))
        return result
    return bezier

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

def get_bezier_path_points(control_points: list[tuple[float,float]], weight: int = 1):
        """
        A general-purpose function for mapping a set of Bezier control points to a larger set
        of output curve points - used for drawing BrushStroke curves and sampling CurveProfiles

        :param control_points: a list of control point coordinates
        :type control_points: list[tuple[float,float]]
        :param weight: an integer which internally multiplies the control points volume - 1 = regular bezier curve, >1 = straighter curves
        :type weight: int
        """
        N_POINTS = 128
        SAMPLE_SPACING = 0.01

        # repeat coords to reduce bezier smoothing; _weighting = level of smoothness
        weighted_path = []
        for coord in control_points:
            weighted_path += [coord,] * weight

        # generate points from bezier (these will be variably spaced based on weighting), then resample by density
        bezier_points = make_bezier(weighted_path)([t/N_POINTS for t in range(0, N_POINTS + 1)])
        return resample_by_arc_length(bezier_points, sample_spacing=SAMPLE_SPACING)