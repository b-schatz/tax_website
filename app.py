from flask import Flask, request, render_template
import plotly.graph_objs as go
import plotly.io as pio
from tax_utils import calculate_taxes, make_tax_breakdown_graph, make_tax_summary_chart, make_income_allocation_chart, make_state_comparison_chart, get_available_states, make_total_sales_tax_chart

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    init_numbers = None
    graph_html = None
    summary_html = None
    allocation_html = None
    comparison_html = None
    sales_html = None
    state_list = get_available_states()

    if request.method == 'POST':
        income = float(request.form['income'])
        status = request.form['status']
        children = int(request.form['children'])
        state = request.form['state']

        spend_pct = float(request.form.get("spend_pct", 50))
        tax_data = calculate_taxes(income, status, children, state, spend_pct)


        _, state_sales_tax, state_sales_tax = make_total_sales_tax_chart(
            state,
            income,
            income - tax_data['total']
        )
        init_numbers = {
            'income': income,
            'status': status,
            'children': children,
            'state': state,
            'spend_pct': spend_pct,
            'standard_deduction': tax_data['standard_deduction'],
            'state_deduction': tax_data['state_deduction'],
            'taxable_income': tax_data['taxable_income'],
            'taxable_state_income': tax_data['taxable_state_income'],
            'taxable_spend': tax_data['taxable_spend']
        }

        result = {
            'total_tax': round(tax_data['total'], 2),
            'effective_rate': round(tax_data['total'] / income * 100, 2),
            'total_fed': round(tax_data['federal'] + tax_data['fica'], 2),
            'effective_fed_rate': round((tax_data['federal'] + tax_data['fica']) / income * 100, 2),
            'total_state': round(tax_data['state'], 2),
            'effective_state_rate': round(tax_data['state'] / income * 100, 2),
            'sales_tax_paid': round(state_sales_tax, 2),
            'effective_sales_tax_rate': round(state_sales_tax / income * 100, 2)

        }

        graph_html = pio.to_html(make_tax_breakdown_graph(
            tax_data['federal_items'],
            tax_data['fed_credit_items'], 
            tax_data['fica_items'],
            tax_data['state_items']
        ), full_html=False)

        summary_html = pio.to_html(make_tax_summary_chart(
            income,
            tax_data['federal'],
            tax_data['fica'],
            tax_data['state']
        ), full_html=False)

        allocation_html = pio.to_html(make_income_allocation_chart(
            income,
            tax_data['federal'],
            tax_data['fica'],
            tax_data['state'],
            tax_data['net_income']
        ), full_html=False)

        comparison_html = pio.to_html(make_state_comparison_chart(
            state,
            income,
            status,
            children
        ), full_html=False)

        sales_fig, _, _= make_total_sales_tax_chart(
            state,
            income,
            income - tax_data['total']
        )
        sales_html = pio.to_html(sales_fig, full_html=False)

    return render_template(
        'index.html',
        init_numbers=init_numbers,
        result=result,
        graph_html=graph_html,
        summary_html=summary_html,
        allocation_html=allocation_html,
        comparison_html=comparison_html,
        state_list=state_list,
        sales_html=sales_html
    )


if __name__ == '__main__':
    app.run(debug=True)
