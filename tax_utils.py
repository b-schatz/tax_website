import plotly.graph_objs as go
import json
import os

from collections import defaultdict

STATE_BRACKETS = defaultdict(lambda: {
    "single": [],
    "married": [],
    "standard_deduction": {},
    "personal_exemption": {}
})

with open("state_tax_brackets_2025.json") as f:
    bracket_data = json.load(f)

for state, info in bracket_data.items():
    for status in ("single", "married"):
        for b in info.get(status, []):
            STATE_BRACKETS[state][status].append(
                (b["bottom"], b["top"], b["rate"]))
        STATE_BRACKETS[state]["standard_deduction"][status] = info.get(
            "standard_deduction", {}).get(status, 0)
        STATE_BRACKETS[state]["personal_exemption"][status] = info.get(
            "personal_exemption", {}).get(status, 0)

with open("state_sales_tax.json") as f:
    STATE_SALES_TAX = json.load(f)


def get_available_states():
    return sorted(STATE_BRACKETS)


def calculate_state_tax(state, status, income, kids):
    if state not in STATE_BRACKETS or not STATE_BRACKETS[state][status]:
        return 0, [("State Income Tax", 0)]

    brackets = STATE_BRACKETS[state].get(status)
    if not brackets:
        return 0, [("State Income Tax", 0)]

    deduction = STATE_BRACKETS[state].get(
        "standard_deduction", {}).get(status, 0)
    exemption = STATE_BRACKETS[state].get(
        "personal_exemption", {}).get(status, 0)

    adjusted_income = max(0, income - deduction - (exemption * kids))
    state_tax = 0
    state_line_items = []
    prev_limit = 0

    for bottom, top, rate in brackets:
        if top <= prev_limit:
            continue
        if adjusted_income > top:
            taxed = top - prev_limit
            tax = taxed * rate
            label = f"${int(prev_limit)}–{int(top)}"
            state_line_items.append((label, tax))
            state_tax += tax
            prev_limit = top
        else:
            taxed = adjusted_income - prev_limit
            tax = taxed * rate
            label = f"${int(prev_limit)}–{int(adjusted_income)}"
            state_line_items.append((label, tax))
            state_tax += tax
            break

    return state_tax, state_line_items


def calculate_taxes(income, status, kids, state):

    brackets = {
        'single': [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37)
        ],
        'married': [
            (23850, 0.10),
            (96950, 0.12),
            (206700, 0.22),
            (394600, 0.24),
            (501050, 0.32),
            (751600, 0.35),
            (float('inf'), 0.37)
        ]
    }

    standard_deductions = {
        'single': 15000,
        'married': 30000
    }

    if status not in brackets or status not in standard_deductions:
        raise ValueError("Unsupported or invalid filing status.")

    taxable_income = max(0, income - standard_deductions[status])
    if taxable_income == 0:
        return {
            'total': 0,
            'fed_line_items': [("Standard Deduction", standard_deductions[status])]
        }
    fed_line_items = []
    state_line_items = []
    total_federal = 0
    previous_limit = 0

    state_deduction = STATE_BRACKETS.get(state, {}).get(
        "standard_deduction", {}).get(status, 0)
    taxable_state_income = max(0, income - state_deduction)

    state_tax, state_line_items = calculate_state_tax(
        state, status, taxable_state_income, kids)

    for top, rate in brackets[status]:
        if taxable_income > top:
            taxed_amount = top - previous_limit
            tax = taxed_amount * rate
            fed_line_items.append((f"${previous_limit}-{top}", tax))
            total_federal += tax
            previous_limit = top
        else:
            taxed_amount = taxable_income - previous_limit
            tax = taxed_amount * rate
            fed_line_items.append((f"${previous_limit}-{taxable_income}", tax))
            total_federal += tax
            break

    ctc = min(kids * 2000, total_federal)
    total_federal -= ctc
    fed_line_items.append(("Child Tax Credit", -ctc))

    social_security_cap = 176100
    ss_tax = min(income, social_security_cap) * 0.062
    medicare_tax = income * 0.0145
    total_fica = ss_tax + medicare_tax

    fica_line_items = [
        ("Social Security (6.2%)", ss_tax),
        ("Medicare (1.45%)", medicare_tax)
    ]
    return {
        'total': total_federal + total_fica + state_tax,
        'total_fed': total_federal + total_fica,
        'federal': total_federal,
        'fica': total_fica,
        'state': state_tax,
        'federal_items': fed_line_items,
        'fica_items': fica_line_items,
        'state_items': state_line_items
    }


def make_tax_breakdown_graph(fed_items, fica_items, state_items):
    import plotly.graph_objs as go

    x_labels = [item[0] for item in fed_items + fica_items + state_items]
    total_length = len(x_labels)

    y_federal = [item[1] for item in fed_items] + \
        [0] * (total_length - len(fed_items))
    y_fica = [0] * len(fed_items) + [item[1] for item in fica_items] + \
        [0] * (total_length - len(fed_items) - len(fica_items))
    y_state = [0] * (total_length - len(state_items)) + [item[1]
                                                         for item in state_items]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Federal Tax',
        x=x_labels,
        y=y_federal,
        marker=dict(line=dict(width=0)),
    ))

    fig.add_trace(go.Bar(
        name='FICA Tax',
        x=x_labels,
        y=y_fica,
        marker=dict(line=dict(width=0)),
    ))

    fig.add_trace(go.Bar(
        name='State Tax',
        x=x_labels,
        y=y_state,
        marker=dict(line=dict(width=0)),
    ))

    combined = [a + b + c for a, b, c in zip(y_federal, y_fica, y_state)]
    label_texts = [f"${int(val):,}" if val >
                   0 else f"({0}%)" for val in combined]

    fig.add_trace(go.Scatter(
        x=x_labels,
        y=combined,
        text=label_texts,
        mode="text",
        textposition="top center",
        showlegend=False
    ))

    fig.update_layout(
        barmode='stack',
        title="Tax Breakdown: Federal + FICA",
        xaxis_title="Line Item",
        yaxis_title="Amount ($)",
        legend=dict(x=0.8, y=1.1)
    )

    return fig


def make_tax_summary_chart(income, federal, fica, state):
    import plotly.graph_objs as go

    tax_categories = ['Federal', 'FICA', 'State',  'Net Income']
    tax_values = [federal, fica, state, income - (federal + fica + state)]
    colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A']

    fig = go.Figure(data=[
        go.Bar(
            x=tax_categories,
            y=tax_values,
            text=[f"${int(v):,}" for v in tax_values],
            textposition='auto',
            marker_color=colors
        )
    ])

    fig.update_layout(
        title="Income Distribution Breakdown",
        xaxis_title="Tax Type",
        yaxis_title="Amount ($)",
        yaxis=dict(tickprefix="$"),
        showlegend=False
    )

    return fig


def make_income_allocation_chart(income, federal, fica, state):
    import plotly.graph_objs as go

    net = income - (federal + fica + state)

    segments = [
        ("Net Income", net, "#FFA15A"),
        ("Federal", federal, "#636EFA"),
        ("FICA", fica, "#EF553B"),
        ("State", state, "#00CC96")
    ]

    fig = go.Figure()

    for name, value, color in segments:
        percentage = value / income * 100 if income > 0 else 0
        label = f"{name}<br>${int(value):,} ({percentage:.1f}%)"
        fig.add_trace(go.Bar(
            x=["Total Income"],
            y=[value],
            name=name,
            marker_color=color,
            text=[label],
            textposition="inside"
        ))

    fig.update_layout(
        barmode='stack',
        height=800,
        title="Income Allocation (100%)",
        yaxis=dict(title="Amount ($)", tickprefix="$", range=[0, income]),
        xaxis=dict(title=""),
        showlegend=True
    )

    return fig


def make_state_comparison_chart(current_state_abbr, income, status, kids):
    state_totals = {}

    for state, data in STATE_BRACKETS.items():
        deduction = data.get("standard_deduction", {}).get(status, 0) or 0
        taxable_income = max(0, income - deduction)

        brackets = data.get(status, [])
        total_tax = 0
        prev = 0

        for bottom, top, rate in brackets:
            if taxable_income > top:
                taxed = top - bottom
                total_tax += taxed * rate
            elif taxable_income > bottom:
                taxed = taxable_income - bottom
                total_tax += taxed * rate
                break

        state_totals[state] = total_tax

    your_tax = state_totals.get(current_state_abbr, 0)

    sorted_states = sorted(state_totals.items(),
                           key=lambda x: x[1], reverse=True)
    labels, values = zip(*sorted_states)

    colors = []
    for state, val in sorted_states:
        if state == current_state_abbr:
            colors.append("blue")
        elif val > your_tax:
            colors.append("red")
        elif val < your_tax:
            colors.append("green")
        else:
            colors.append("gray")

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        text=[f"${v:,.0f}" for v in values],
        textposition="auto"
    ))

    fig.update_layout(
        title="State Income Tax Comparison (2025)",
        xaxis_title="State",
        yaxis_title="Total State Income Tax ($)",
        yaxis_tickprefix="$",
        height=500
    )

    return fig


def make_total_sales_tax_chart(current_state_abbr, income, net_income, spend_pct):
    spend_fraction = spend_pct / 100.0
    taxable_spend = net_income * spend_fraction

    state_totals = {}

    for state, sales_data in STATE_SALES_TAX.items():
        state_rate = sales_data.get("state_rate", 0)
        local_rate = sales_data.get("avg_local_rate", 0)
        total_sales_rate = state_rate + local_rate
        sales_tax_paid = taxable_spend * total_sales_rate
        state_totals[state] = sales_tax_paid

    sorted_states = sorted(state_totals.items(),
                           key=lambda x: x[1], reverse=True)
    labels, values = zip(*sorted_states)

    your_tax = state_totals.get(current_state_abbr, 0)
    state_sales_tax = your_tax
    colors = []
    for state, val in sorted_states:
        if state == current_state_abbr:
            colors.append("blue")
        elif val > your_tax:
            colors.append("red")
        elif val == your_tax:
            colors.append("grey")
        else:
            colors.append("green")

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        text=[f"${v:,.0f}" for v in values],
        textposition="auto"
    ))

    fig.update_layout(
        title=f"Estimated Sales Tax on {int(spend_pct)}% of Net Income",
        xaxis_title="State",
        yaxis_title="Sales Tax Paid ($)",
        yaxis_tickprefix="$",
        height=500
    )

    return fig, state_sales_tax, sales_tax_paid
