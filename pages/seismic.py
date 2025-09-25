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

        # Define pre_filter once for consistent use
        pre_filter = (0.005, 0.006, 30.0, 35.0)

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
        stream_vel.remove_response(inventory=inv, output='VEL', pre_filt=pre_filter)
        plot_stream(stream_vel,
                    title="Seismic Data - Velocity (m/s)",
                    yaxis_title="Velocity (m/s)",
                    unit_label="m/s",
                    filename_html="static/plots/velocity.html")

        # === Step 4: Acceleration (m/s²) ===
        stream_acc = stream.copy()
        stream_acc.remove_response(inventory=inv, output='ACC', pre_filt=pre_filter)
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
    Returns raw data (counts) with instrument response attached.
    """
    if channels is None:
        channels = ['EHZ']

    client = Client('RASPISHAKE')
    # Fixed: use 'response' instead of 'RESP' for full instrument response
    inv = client.get_stations(network='AM', station=station, level='response')

    stream = Stream()
    for ch in channels:
        try:
            trace = client.get_waveforms('AM', station, '00', ch, start, end)
            stream += trace
            print(f"Fetched {len(trace)} traces for channel {ch}")
        except Exception as e:
            print(f"Warning: Could not fetch data for channel {ch}: {e}")

    # Merge traces to handle any overlaps or gaps
    if len(stream) > 1:
        print(f"Merging {len(stream)} traces for {station} {ch}")
        stream.merge(fill_value='interpolate')

    # Attach instrument response (optional but good practice)
    stream.attach_response(inv)

    # Print trace info for debugging
    for tr in stream:
        print(f"Trace: {tr.stats.channel}, {len(tr.data)} samples, {tr.stats.starttime} to {tr.stats.endtime}")

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
    Fixed: Only one subplot regardless of number of traces.
    """
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(filename_html), exist_ok=True)

    # If multiple traces, merge them first or select the best one
    if len(stream) > 1:
        print(f"Multiple traces found ({len(stream)}), merging...")
        # Try to merge traces
        try:
            stream_merged = stream.copy()
            stream_merged.merge(fill_value='interpolate')
            if len(stream_merged) == 1:
                stream = stream_merged
                print("Successfully merged traces into single trace")
            else:
                # If merge fails, take the longest trace
                longest_trace = max(stream, key=lambda tr: len(tr.data))
                stream = Stream(traces=[longest_trace])
                print(f"Using longest trace: {longest_trace.stats.channel}, {len(longest_trace.data)} samples")
        except Exception as e:
            # Fallback: take first trace
            stream = Stream(traces=[stream[0]])
            print(f"Fallback: using first trace {stream[0].stats.channel}: {e}")

    # Now we should have exactly one trace
    if len(stream) != 1:
        print(f"Warning: Still have {len(stream)} traces after processing, using first one")
        stream = Stream(traces=[stream[0]])

    trace = stream[0]

    # Create single subplot
    fig = make_subplots(rows=1, cols=1,
                        subplot_titles=[f"{trace.stats.channel}"],
                        specs=[[{"secondary_y": False}]])

    try:
        data, times = downsample_trace(trace)
        times_dt = trace_to_datetime(trace, times)

        fig.add_trace(go.Scatter(
            x=times_dt, y=data,
            name=f"{trace.stats.channel} ({unit_label})",
            line=dict(width=1, color='red'),
            mode='lines'
        ), row=1, col=1)
    except Exception as e:
        print(f"Warning: Could not plot trace {trace.stats.channel}: {e}")
        # Create empty plot as fallback
        fig.add_trace(go.Scatter(x=[], y=[], name="No Data"))

    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            font=dict(size=16)
        ),
        xaxis_title="Time (Mountain Time)",
        yaxis_title=yaxis_title,
        height=300,
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=50, r=50, t=80, b=50),
        showlegend=False
    )

    # Configure modebar to only show essential tools
    config = {
        'modeBarButtons': [
            ['toImage', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'resetScale2d']
        ],
        'displaylogo': False,
        'toImageButtonOptions': {
            'format': 'svg',
            'filename': 'seismic_plot',
            'height': 300,
            'width': 1200,
            'scale': 2  # Higher quality SVG
        }
    }

    # Add white background with gridlines
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='lightgray',
        showline=True,
        linewidth=1,
        linecolor='black',
        rangeslider_visible=False  # Disable rangeslider for cleaner look
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

    # Also save as SVG for static use if requested
    if filename_svg:
        try:
            fig.write_image(filename_svg, width=1200, height=300, scale=2)
        except Exception as e:
            print(f"Warning: Could not save SVG {filename_svg}: {e}")

    print(f"Saved plot: {filename_html}")


def register(app):
    from flask import render_template
    import time

    @app.route('/seismic', methods=['GET'])
    def seismic():
        # Generate cache buster based on 5-minute intervals to match plot update frequency
        cache_buster = int(time.time() // 300)  # Updates every 5 minutes
        return render_template('seismic/seismic.html', cache_buster=cache_buster)

    # Start background thread for plot generation
    if not hasattr(app, '_plot_thread_started'):
        plot_thread = threading.Thread(target=plot_updater, daemon=True)
        plot_thread.start()
        app._plot_thread_started = True
        print("Started seismic plot updater thread")
