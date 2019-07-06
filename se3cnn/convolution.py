# pylint: disable=C,R,E1101,E1102
import torch
from se3cnn import SE3Kernel
from se3cnn.point_kernel import SE3PointKernel
from se3cnn import kernel, point_kernel, point_utils


class SE3Convolution(torch.nn.Module):
    def __init__(self, Rs_in, Rs_out, size, radial_window=kernel.gaussian_window_wrapper, dyn_iso=False, verbose=False, **kwargs):
        super().__init__()

        self.kernel = SE3Kernel(Rs_in, Rs_out, size, radial_window=radial_window, dyn_iso=dyn_iso, verbose=verbose)
        self.kwargs = kwargs

    def __repr__(self):
        return "{name} ({kernel}, kwargs={kwargs})".format(
            name=self.__class__.__name__,
            kernel=self.kernel,
            kwargs=self.kwargs,
        )

    def forward(self, input):  # pylint: disable=W
        return torch.nn.functional.conv3d(input, self.kernel(), **self.kwargs)


class SE3ConvolutionTranspose(torch.nn.Module):
    def __init__(self, Rs_in, Rs_out, size, radial_window=kernel.gaussian_window_wrapper, dyn_iso=False, verbose=False, **kwargs):
        super().__init__()

        self.kernel = SE3Kernel(Rs_out, Rs_in, size, radial_window=radial_window, dyn_iso=dyn_iso, verbose=verbose)
        self.kwargs = kwargs

    def __repr__(self):
        return "{name} ({kernel}, kwargs={kwargs})".format(
            name=self.__class__.__name__,
            kernel=self.kernel,
            kwargs=self.kwargs,
        )

    def forward(self, input):  # pylint: disable=W
        return torch.nn.functional.conv_transpose3d(input, self.kernel(), **self.kwargs)


class SE3PointConvolution(torch.nn.Module):
    def __init__(self, Rs_in, Rs_out, radii,
                 radial_function=point_kernel.gaussian_radial_function,
                 J_filter_max=10, PointKernel=SE3PointKernel, sh_backwardable=False, **kwargs):
        super().__init__()

        self.kernel = PointKernel(Rs_in, Rs_out, radii,
                             radial_function=radial_function,
                             J_filter_max=J_filter_max,
                             sh_backwardable=sh_backwardable)
        self.kwargs = kwargs

    def __repr__(self):
        return "{name} ({kernel}, kwargs={kwargs})".format(
            name=self.__class__.__name__,
            kernel=self.kernel,
            kwargs=self.kwargs,
        )

    def forward(self, input, difference_mat, relative_mask=None):  # pylint: disable=W
        """
        :param input: tensor [[batch], channel, points]
        :param difference_mat: tensor [[batch], points, points, xyz]
        :param relative_mask: [[batch], points, points]
        """

        k = self.kernel(difference_mat)

        if input.dim() == 2:
            # No batch dimension
            if relative_mask is not None:
                k = torch.einsum('ba,dcba->dcba', (relative_mask, k))
            output = torch.einsum('ca,dcba->db', (input, k))
        elif input.dim() == 3:
            # Batch dimension
            # Apply relative_mask to kernel (if examples are not all size N, M)
            if relative_mask is not None:
                k = torch.einsum('nba,dcnba->dcnba', (relative_mask, k))
            output = torch.einsum('nca,dcnba->ndb', (input, k))

        return output


class SE3PointNeighborConvolution(torch.nn.Module):
    def __init__(self, Rs_in, Rs_out, radii, radial_function=point_kernel.gaussian_radial_function, J_filter_max=10, **kwargs):
        super().__init__()

        self.kernel = SE3PointKernel(Rs_in, Rs_out, radii, radial_function=radial_function, J_filter_max=J_filter_max)
        self.kwargs = kwargs

    def __repr__(self):
        return "{name} ({kernel}, kwargs={kwargs})".format(
            name=self.__class__.__name__,
            kernel=self.kernel,
            kwargs=self.kwargs,
        )

    def forward(self, input, coords=None, neighbors=None, relative_mask=None):  # pylint: disable=W
        if coords is None or neighbors is None:
            raise ValueError()
        difference_matrix = point_utils.neighbor_difference_matrix(neighbors, coords)  # [N, K, 3]
        neighbors_input = point_utils.neighbor_feature_matrix(neighbors, input)  # [C, N, K]
        k = self.kernel(difference_matrix)

        if input.dim() == 2:
            # No batch dimension
            if relative_mask is not None:
                k = torch.einsum('ba,dcba->dcba', (relative_mask, k))
            output = torch.einsum('cba,dcba->db', (neighbors_input, k))
        elif input.dim() == 3:
            # Batch dimension
            # Apply relative_mask to kernel (if examples are not all size N, M)
            if relative_mask is not None:
                k = torch.einsum('nba,dcnba->dcnba', (relative_mask, k))
            output = torch.einsum('ncba,dcnba->ndb', (neighbors_input, k))

        return output


