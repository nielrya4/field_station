from obspy.clients.fdsn import Client
from obspy.core import UTCDateTime, Stream
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import threading
import time
import os
from datetime import timezone
import pytz

def generate_plots():
    try:
        end = UTCDateTime() - 60
        start = end - (12 * 60 * 60)

        station = 'SAABC'
        channels = ['EHZ']

        # === Step 1: Get data ===
        stream, inv = get_seismic_data(station, start, end, channels)

        # === Step 2: Raw Counts ===
        plot_stream(stream,
                    title="Raw Seismic Data (Counts)",
                    yaxis_title="Counts",
                    unit_label="raw counts",
                    filename_html="static/plots/counts.html")

        # === Step 3: Velocity (m/s) ===
        stream_vel = stream.copy()
        stream_vel.remove_response(output='VEL')
        plot_stream(stream_vel,
                    title="Seismic Data - Velocity (m/s)",
                    yaxis_title="Velocity (m/s)",
                    unit_label="m/s",
                    filename_html="static/plots/velocity.html")

        # === Step 4: Acceleration (m/s²) ===
        stream_acc = stream.copy()
        stream_acc.remove_response(output='ACC')
        plot_stream(stream_acc,
                    title="Seismic Data - Acceleration (m/s²)",
                    yaxis_title="Acceleration (m/s²)",
                    unit_label="m/s²",
                    filename_html="static/plots/acceleration.html")
        
        print(f"Plots generated at {UTCDateTime()}")
    except Exception as e:
        print(f"Error generating plots: {e}")

def plot_updater():
    while True:
        generate_plots()
        time.sleep(300)  # 5 minutes

def get_seismic_data(station, start, end, channels=None):
    """
    Fetch raw seismic waveforms from the RASPISHAKE server for a given station.
    """
    if channels is None:
        channels = ['EHZ']
        
    client = Client('RASPISHAKE')
    inv = client.get_stations(network='AM', station=station, level='RESP')

    stream = Stream()
    for ch in channels:
        trace = client.get_waveforms('AM', station, '00', ch, start, end)
        stream += trace

    # Attach instrument response
    stream.attach_response(inv)
    return stream, inv


def downsample_trace(trace, max_points=10000, target_points=5000):
    """
    Downsample trace data if too large for plotting.
    """
    data = trace.data
    times = trace.times()
    if len(data) > max_points:
        step = len(data) // target_points
        data = data[::step]
        times = times[::step]
    return data, times


def trace_to_datetime(trace, times):
    """
    Convert ObsPy times to datetime using trace starttime, converted to Mountain Time.
    """
    # Get UTC start time
    start_time_utc = trace.stats.starttime.datetime.replace(tzinfo=timezone.utc)
    
    # Convert to Mountain Time (automatically handles MST/MDT)
    mountain_tz = pytz.timezone('US/Mountain')
    start_time_mt = start_time_utc.astimezone(mountain_tz)
    
    # Create time series in Mountain Time
    return [start_time_mt + pd.Timedelta(seconds=t) for t in times]


def plot_stream(stream, title, yaxis_title, unit_label, filename_html, filename_svg=None):
    """
    Create an interactive Plotly plot for a stream of seismic traces.
    """
    fig = make_subplots(rows=len(stream), cols=1,
                        subplot_titles=[f"{tr.stats.channel}" for tr in stream],
                        shared_xaxes=True)

    for i, tr in enumerate(stream):
        data, times = downsample_trace(tr)
        times_dt = trace_to_datetime(tr, times)

        fig.add_trace(go.Scatter(
            x=times_dt, y=data,
            name=f"{tr.stats.channel} ({unit_label})",
            line=dict(width=1, color='green')
        ), row=i + 1, col=1)

    fig.update_layout(
        title=title,
        xaxis_title="Time (Mountain Time)",
        yaxis_title=yaxis_title,
        height=300 * len(stream),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    # Configure modebar to only show zoom in, zoom out, reset axes, and download as SVG
    config = {
        'modeBarButtons': [
            ['toImage', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'resetScale2d']
        ],
        'displaylogo': False,
        'toImageButtonOptions': {
            'format': 'svg',
            'filename': 'seismic_plot',
            'height': 300 * len(stream),
            'width': 1000,
            'scale': 1
        }
    }
    
    # Add white background with gridlines for all subplots
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray',
        showline=True,
        linewidth=1,
        linecolor='black'
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray',
        showline=True,
        linewidth=1,
        linecolor='black'
    )
    # Save as HTML for fast loading
    fig.write_html(filename_html, config=config)
    if filename_svg:
        fig.write_image(filename_svg)


def register(app):
    from flask import render_template
    
    @app.route('/seismic', methods=['GET'])
    def seismic():
        return render_template('seismic/seismic.html')

    # Start background thread for plot generation
    plot_thread = threading.Thread(target=plot_updater, daemon=True)
    plot_thread.start()



