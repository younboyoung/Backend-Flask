from boto3 import session
from sqlalchemy import func
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
from datetime import datetime
from flask import Blueprint, render_template, redirect, request, url_for, abort, send_file, Response
from wtforms.validators import Email
from apps.common.auth import api_signin_required, signin_required
from apps.controllers.index.forms import CreateForm
from flask_login import current_user
from apps.database.models import Ecg, User
from apps.database.session import db
from config import Config
from apps.common.response import ok, error
from werkzeug.utils import secure_filename
import os
from io import BytesIO
from apps.service.pc_service import calculatePc


app = Blueprint('index', __name__, url_prefix='/index', static_url_path='/static')

#font_fname = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
#font_name = font_manager.FontProperties(fname=font_fname).get_name()
#rc('font', family=font_name)
#plt.rcParams["font.family"] = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'

plt.rcParams["font.family"] = 'NanumGothic'

@app.route('', methods=['GET'])
@signin_required
def index():
    args = request.args
    page = int(args.get('page') or 1)
    per_page = 1

    pagination1 = Ecg.query.filter(Ecg.user_id == current_user.id).order_by(Ecg.id.desc()).paginate(page, per_page, error_out=False)
    ecgs1 = pagination1.items

    ecgs2_test = db.session.execute('select local as local, count(*) as count, count(case when stress = 1 then 1 end) as stress_count from ecg where ecg.user_id = :id group by local order by (count(case when stress = 1 then 1 end) / count(*)) desc;', {'id': current_user.id})
    stress_count = []
    stress_local = []
    for ecg in ecgs2_test:
        if (ecg.stress_count / ecg.count) > 0:
            stress_count.append(round((ecg.stress_count / ecg.count), 2))
            stress_local.append(ecg.local)

    ecgs2 = db.session.execute('select local as local, count(*) as count, count(case when stress = 1 then 1 end) as stress_count from ecg where ecg.user_id = :id group by local order by (count(case when stress = 1 then 1 end) / count(*)) desc;', {'id': current_user.id})
    
    ecgs3 = db.session.execute('select * from ecg where ecg.user_id = :id and ecg.arrhythmia = 1 order by id desc limit 3', {'id': current_user.id})
    row = ecgs3.fetchone()
    
    return render_template('home.html', ecgs1=ecgs1, pagination1=pagination1, ecgs2=ecgs2, ecgs3=ecgs3, row=row, stress_count=stress_count, stress_local=stress_local)

@app.route('/plot')
def plot():

    stress = db.session.execute('select local, rri_avg from ecg where ecg.user_id = :id order by id desc', {'id': current_user.id})
    stress = pd.DataFrame(stress)

    aa, bb = [], []
    for i in range(len(stress)):
        nnnnnnnn = str(stress[0][i])
        aa.append(nnnnnnnn) # 장소
        bb.append(int(stress[1][i])) # 수치

    plt.plot(aa, bb, '^', color = 'violet', label = 'RRI Avg') # 각 데이터
    plt.axhline(431.36877612981704, color = 'purple', linewidth = 2, label = 'Threshold') #안정적 상태의 문턱치
    plt.xlabel('Place')
    plt.ylabel('RRI Avg')
    plt.legend(loc='upper right')
    img = BytesIO()
    plt.savefig(img, format='png',dpi=200)
    img.seek(0)
    plt.close()
    return send_file(img, mimetype='image/png')

@app.route('/create', methods=['GET','POST'])
@signin_required
def create():
    form = CreateForm()

    if form.validate_on_submit():
        datafile = form.datafile.data
        data2 = pd.read_csv(datafile, encoding = 'utf-8', engine = 'python', index_col = False)
        dates = data2[1:2]['박 헌'].values
        data2 = data2.drop(['박 헌'], axis = 1)
        data2 = data2[2511:-2500]
        data2 = data2.astype('float')
        data2.columns = [0]
        data2 = data2.reset_index()
        data2 = data2.drop(['index'], axis = 1)
    
        pac, pvc, threshold, stress, image_url_pc = calculatePc(data2, dates)

        pc = False
        if(pac == True or pvc == True): pc = True
        
        ecg = Ecg(local=form.local.data, user_id = current_user.id, pac = pac, pvc = pvc, arrhythmia=pc, stress=stress, rri_avg=threshold[0][1], image_pc = image_url_pc, measured_date=dates[0])
        db.session.add(ecg)
        db.session.commit()
        
        return redirect(url_for('index.index'))

    return render_template('create.html', form=form)


@app.route('/<int:ecg_id>', methods=['DELETE'])
@api_signin_required
def delete(ecg_id):
    ecg = Ecg.query.filter(Ecg.id == ecg_id).first()
    if not ecg:
        return error(40400)
    if current_user.id != ecg.user_id:
        return error(40300)

    db.session.delete(ecg)
    db.session.commit()
    return ok()
