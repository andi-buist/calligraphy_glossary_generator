import math

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

def evaluate_catmull_rom_segment(
    p0: tuple[float, float], 
    p1: tuple[float, float], 
    p2: tuple[float, float], 
    p3: tuple[float, float], 
    num_points: int,
    alpha: float = 1.0
) -> list[tuple[float, float]]:
    """
    Evaluates a single centripetal Catmull-Rom segment between p1 and p2.
    alpha=0.5 (centripetal) prevents cusps and overshoot on sharp turns.
    """
    if num_points <= 1:
        return [p1]

    def tj(ti: float, pi: tuple[float, float], pj: tuple[float, float]) -> float:
        dist = math.hypot(pj[0] - pi[0], pj[1] - pi[1])
        return ti + (dist ** alpha) if dist > 0 else ti + 1e-6

    t0 = 0.0
    t1 = tj(t0, p0, p1)
    t2 = tj(t1, p1, p2)
    t3 = tj(t2, p2, p3)

    segment_points = []
    # Avoid division by zero if control points are overlapping
    if abs(t2 - t1) < 1e-6:
        return [p1] * num_points

    for i in range(num_points):
        # Linearly space t between t1 and t2
        t = t1 + (t2 - t1) * (i / (num_points - 1))
        
        # De Casteljau-like evaluation for Catmull-Rom
        a1_x = ((t1 - t) * p0[0] + (t - t0) * p1[0]) / (t1 - t0)
        a1_y = ((t1 - t) * p0[1] + (t - t0) * p1[1]) / (t1 - t0)
        a2_x = ((t2 - t) * p1[0] + (t - t1) * p2[0]) / (t2 - t1)
        a2_y = ((t2 - t) * p1[1] + (t - t1) * p2[1]) / (t2 - t1)
        a3_x = ((t3 - t) * p2[0] + (t - t2) * p3[0]) / (t3 - t2)
        a3_y = ((t3 - t) * p2[1] + (t - t2) * p3[1]) / (t3 - t2)

        b1_x = ((t2 - t) * a1_x + (t - t0) * a2_x) / (t2 - t0)
        b1_y = ((t2 - t) * a1_y + (t - t0) * a2_y) / (t2 - t0)
        b2_x = ((t3 - t) * a2_x + (t - t1) * a3_x) / (t3 - t1)
        b2_y = ((t3 - t) * a2_y + (t - t1) * a3_y) / (t3 - t1)

        c_x = ((t2 - t) * b1_x + (t - t1) * b2_x) / (t2 - t1)
        c_y = ((t2 - t) * b1_y + (t - t1) * b2_y) / (t2 - t1)

        segment_points.append((c_x, c_y))
        
    return segment_points

def get_segmented_path_points(control_points: list[tuple[float, float]], weight: float) -> list[tuple[float, float]]:
    """
    Constructs a continuous piece-wise spline across all control points.
    Extrapolates virtual endpoints to ensure the curve starts at index 0 and ends at index -1.
    """
    N_POINTS = 64
    SAMPLE_SPACING = 0.01

    n = len(control_points)
    if n < 2:
        return control_points
    
    # If only 2 points, a straight line is the only deterministic path
    if n == 2:
        return [
            (control_points[0][0] + (control_points[1][0] - control_points[0][0]) * (i / (N_POINTS - 1)),
             control_points[0][1] + (control_points[1][1] - control_points[0][1]) * (i / (N_POINTS - 1)))
            for i in range(N_POINTS)
        ]

    # Synthesize bounding points to clamp the boundary tangents cleanly
    p_start = (2 * control_points[0][0] - control_points[1][0], 2 * control_points[0][1] - control_points[1][1])
    p_end = (2 * control_points[-1][0] - control_points[-2][0], 2 * control_points[-1][1] - control_points[-2][1])
    
    extended_pts = [p_start] + control_points + [p_end]
    spline_points = []

    # Evaluate each localized interval independently
    for i in range(1, len(extended_pts) - 2):
        segment = evaluate_catmull_rom_segment(
            extended_pts[i-1], 
            extended_pts[i], 
            extended_pts[i+1], 
            extended_pts[i+2], 
            num_points=N_POINTS,
            alpha=weight
        )
        # Drop the last point of the segment to prevent duplicate points where segments stitch together
        if i < len(extended_pts) - 3:
            spline_points.extend(segment[:-1])
        else:
            spline_points.extend(segment)

    return resample_by_arc_length(spline_points, sample_spacing=SAMPLE_SPACING)