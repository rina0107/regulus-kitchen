from flask import Flask, render_template, request, redirect, session, url_for
import json
import os

app = Flask(__name__)
app.secret_key = 'regulus_secret_key'  # セッション用の秘密鍵

DATA_FILE = 'data.json'

# データ読み込み
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"menus": [], "recipes": {}, "members": []}

# データ保存
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ----------------------------------------------------
# 🏠 トップ画面（献立一覧）
# ----------------------------------------------------
@app.route('/')
def index():
    data = load_data()
    is_admin = session.get('is_admin', False)
    return render_template('index.html', menus=data.get('menus', []), is_admin=is_admin)

# ----------------------------------------------------
# 🔑 ログイン・ログアウト処理
# ----------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == '藤波':
            session['is_admin'] = True
            return redirect('/')
        else:
            return render_template('login.html', error="パスワードが違います")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect('/')

# ----------------------------------------------------
# 📅 献立の追加
# ----------------------------------------------------
@app.route('/add', methods=['GET', 'POST'])
def add_menu():
    if not session.get('is_admin'):
        return redirect('/')
    
    if request.method == 'POST':
        data = load_data()
        new_menu = {
            "date": request.form.get('date'),
            "breakfast": request.form.get('breakfast'),
            "lunch": request.form.get('lunch'),
            "dinner": request.form.get('dinner')
        }
        data.setdefault('menus', []).append(new_menu)
        save_data(data)
        return redirect('/')
        
    return render_template('add.html')

# ----------------------------------------------------
# 📖 レシピ一覧 & 追加・削除
# ----------------------------------------------------
@app.route('/recipes')
def recipe_list():
    data = load_data()
    is_admin = session.get('is_admin', False)
    return render_template('recipes.html', recipes=data.get('recipes', {}), is_admin=is_admin)

# 💡 レシピの新規追加（管理者のみ）
@app.route('/recipe/add', methods=['POST'])
def add_recipe():
    if not session.get('is_admin'):
        return redirect('/recipes')
        
    dish_name = request.form.get('dish_name')
    ingredients = request.form.get('ingredients', '')
    instructions = request.form.get('instructions', '')
    
    if dish_name:
        data = load_data()
        data.setdefault('recipes', {})
        data['recipes'][dish_name] = {
            "ingredients": ingredients,
            "instructions": instructions
        }
        save_data(data)
        
    return redirect('/recipes')

# 💡 レシピの削除（管理者のみ）
@app.route('/recipe/<dish_name>/delete')
def delete_recipe(dish_name):
    if not session.get('is_admin'):
        return redirect('/recipes')
        
    data = load_data()
    if 'recipes' in data and dish_name in data['recipes']:
        del data['recipes'][dish_name]
        save_data(data)
        
    return redirect('/recipes')

# ----------------------------------------------------
# 🍳 レシピ表示（見る・作る）
# ----------------------------------------------------
@app.route('/recipe/<dish_name>')
def show_recipe(dish_name):
    data = load_data()
    recipe = data.get('recipes', {}).get(dish_name, {})
    is_admin = session.get('is_admin', False)
    return render_template('recipe_detail.html', dish_name=dish_name, recipe=recipe, is_admin=is_admin)

# ----------------------------------------------------
# ✏️ レシピ編集（管理者のみ）
# ----------------------------------------------------
@app.route('/recipe/<dish_name>/edit', methods=['GET', 'POST'])
def edit_recipe(dish_name):
    if not session.get('is_admin'):
        return redirect(f'/recipe/{dish_name}')

    data = load_data()
    
    if request.method == 'POST':
        ingredients = request.form.get('ingredients', '')
        instructions = request.form.get('instructions', '')
        
        if 'recipes' not in data:
            data['recipes'] = {}
            
        data['recipes'][dish_name] = {
            "ingredients": ingredients,
            "instructions": instructions
        }
        save_data(data)
        return redirect(f'/recipe/{dish_name}')

    recipe = data.get('recipes', {}).get(dish_name, {})
    return render_template('recipe_edit.html', dish_name=dish_name, recipe=recipe, is_admin=True)

# ----------------------------------------------------
# 🛒 買い出し一覧 & メンバー順繰り割り当て
# ----------------------------------------------------
@app.route('/shopping')
def shopping():
    data = load_data()
    is_admin = session.get('is_admin', False)
    
    menus = data.get('menus', [])
    raw_members = data.get('members', [])
    member_names = [m.get('name') if isinstance(m, dict) else m for m in raw_members]
    
    if member_names:
        offset = 0
        for idx, menu in enumerate(menus):
            if 'shift_offset' in menu:
                offset += menu['shift_offset']
            assigned_buyer = member_names[(idx + offset) % len(member_names)]
            menu['buyer'] = assigned_buyer
            
    return render_template(
        'shopping.html', 
        menus=menus, 
        recipes=data.get('recipes', {}), 
        members=raw_members, 
        is_admin=is_admin
    )

@app.route('/change_buyer/<path:menu_date>')
def change_buyer(menu_date):
    if not session.get('is_admin'):
        return redirect('/shopping')
        
    data = load_data()
    for menu in data.get('menus', []):
        if menu.get('date') == menu_date:
            menu['shift_offset'] = menu.get('shift_offset', 0) + 1
            break
            
    save_data(data)
    return redirect('/shopping')

@app.route('/add_member', methods=['POST'])
def add_member():
    if not session.get('is_admin'):
        return redirect('/shopping')
        
    member_name = request.form.get('member_name')
    if member_name:
        data = load_data()
        data.setdefault('members', [])
        if member_name not in data['members']:
            data['members'].append(member_name)
            save_data(data)
            
    return redirect('/shopping')

@app.route('/delete_member/<member_name>')
def delete_member(member_name):
    if not session.get('is_admin'):
        return redirect('/shopping')
        
    data = load_data()
    if 'members' in data:
        data['members'] = [
            m for m in data['members'] 
            if (m.get('id') if isinstance(m, dict) else m) != member_name 
            and (m.get('name') if isinstance(m, dict) else m) != member_name
        ]
        save_data(data)
        
    return redirect('/shopping')

if __name__ == '__main__':
    app.run(debug=True)