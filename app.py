from flask import Flask, render_template, request, Markup, flash, redirect, url_for, session
import plotly.graph_objects as go
import numpy as np
import plotly.io as pio
from werkzeug.utils import secure_filename
import os
import h5py
import tempfile

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()  # Temporary directory for uploads
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Max upload - 16 MB

ALLOWED_EXTENSIONS = {'hdf5', 'h5'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def add_wall_with_normal(fig, wall_points, normal, centroid, wall_name, edge_identifiers):
    hover_texts = [f"{id}" for id in edge_identifiers]
    fig.add_trace(go.Scatter3d(x=wall_points[:, 0], y=wall_points[:, 1], z=wall_points[:, 2],
                               mode='markers', marker=dict(size=4), name=f'{wall_name} Points',
                               text=hover_texts, hoverinfo='text'))
    fig.add_trace(go.Cone(x=[centroid[0]], y=[centroid[1]], z=[centroid[2]],
                          u=[normal[0]], v=[normal[1]], w=[normal[2]],
                          sizemode="absolute", sizeref=2, showscale=False,
                          colorscale=[[0, 'red'], [1, 'red']], name=f'{wall_name} Normal'))

def view_wall(file_path, wall_name_to_view, excluded_edges=[]):
    wall_normals = {}
    polypoints_all_edges = []
    edge_identifiers = []
    input_wall_index = int(wall_name_to_view.split('_')[1]) - 1

    with h5py.File(file_path, 'r') as file:
        for wall_name in file['Wall_set']:
            if wall_name.startswith('Wall'):
                plane_equation = file[f'Wall_set/{wall_name}/Plane_equation'][()]
                normal = plane_equation[:3]
                wall_normals[wall_name] = normal

        for wall_key in file['Wall_set'].keys():
            wall_group = file[f'Wall_set/{wall_key}']
            for edge_key in wall_group.keys():
                if edge_key.startswith('Edge_') and f"{wall_key}/{edge_key}" not in excluded_edges:
                    edge_group = wall_group[edge_key]
                    edge_idx_dataset = edge_group['Edge_idx'][:]
                    if input_wall_index in edge_idx_dataset:
                        edge_polypoints = edge_group['Polypoints'][:]
                        polypoints_all_edges.extend(edge_polypoints)
                        identifier = f"{wall_key}/{edge_key}"
                        edge_identifiers.extend([identifier] * len(edge_polypoints))

    if polypoints_all_edges:
        polypoints_all_edges = np.array(polypoints_all_edges)
        centroid = np.mean(polypoints_all_edges, axis=0)
        normal = wall_normals[wall_name_to_view]
        fig = go.Figure()
        add_wall_with_normal(fig, polypoints_all_edges, normal, centroid, wall_name_to_view, edge_identifiers)
        tip_of_cone = centroid + normal * 10
        fig.update_layout(scene_camera=dict(eye=dict(x=tip_of_cone[0], y=tip_of_cone[1], z=tip_of_cone[2]),
                                            center=dict(x=centroid[0], y=centroid[1], z=centroid[2]),
                                            up=dict(x=0, y=0, z=1)),
                          scene=dict(xaxis_title='X Axis', yaxis_title='Y Axis', zaxis_title='Z Axis'),
                          title=f'Visualization of {wall_name_to_view}',
                          scene_aspectmode='auto')
                          
        fig_html = pio.to_html(fig, full_html=False)
        return fig_html
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    fig_html = None
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            wall_name_to_view = request.form['wallName']
            excluded_edges = request.form.get('excludedEdges', '').split(',')
            excluded_edges = [edge.strip() for edge in excluded_edges if edge.strip()]
            fig_html = view_wall(file_path, wall_name_to_view, excluded_edges)
            os.remove(file_path)  # Clean up uploaded file
    return render_template('index.html', fig_html=Markup(fig_html) if fig_html else None)

if __name__ == '__main__':
    app.run(debug=True)
